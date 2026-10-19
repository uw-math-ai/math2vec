import Mathlib
import Lean

namespace Wiggle

def jsonEscape (s : String) : String :=
  let chars := (s.toList.map fun
    | '"' => ['\\', '"']
    | '\\' => ['\\', '\\']
    | '\n' => ['\\', 'n']
    | '\r' => ['\\', 'r']
    | '\t' => ['\\', 't']
    | c => [c]).flatten
  String.ofList chars

def jsonField (key value : String) : String :=
  "\"" ++ jsonEscape key ++ "\":\"" ++ jsonEscape value ++ "\""

def jsonNatField (key : String) (value : Nat) : String :=
  "\"" ++ jsonEscape key ++ "\":" ++ toString value

def jsonObject (fields : List String) : String :=
  "{" ++ String.intercalate "," fields ++ "}"

def jsonStrArrayField (key : String) (values : List String) : String :=
  let items := values.map fun v => "\"" ++ jsonEscape v ++ "\""
  "\"" ++ jsonEscape key ++ "\":[" ++ String.intercalate "," items ++ "]"

open Lean Elab Command Meta in
elab "#wiggle_dump_instances" : command => do
  let env ← getEnv
  env.constants.forM fun name info => do
    let isInst ← Command.liftCoreM <| Lean.Meta.isInstance name
    if isInst then
      let typeFmt ← liftTermElabM <| Meta.ppExpr info.type
      let priority? ← Command.liftCoreM <| Lean.Meta.getInstancePriority? name
      let attrKind? ← Command.liftCoreM <| Lean.Meta.getInstanceAttrKind? name
      let priority := match priority? with
        | some n => n
        | none => 1000
      let attrKind := match attrKind? with
        | some .global => "global"
        | some .scoped => "scoped"
        | some .local => "local"
        | none => "none"
      IO.println <| jsonObject [
        jsonField "name" (toString name),
        jsonField "type" typeFmt.pretty,
        jsonNatField "priority" priority,
        jsonField "attrKind" attrKind
      ]

-- Dump the typeclass `extends` hierarchy for every class in the environment.
-- For each class we emit its direct parent structures (the classes it extends),
-- which is the "weakening" direction. The Python side reverses this to obtain
-- children. This replaces the hand-maintained hierarchy in typeclass_mutate.py
-- with a complete, Mathlib-version-accurate one.
--
-- `name` / `parents` are fully-qualified Lean names; the consumer derives short
-- names by taking the last dotted component.
open Lean Elab Command Meta in
elab "#wiggle_dump_class_hierarchy" : command => do
  let env ← getEnv
  env.constants.forM fun name _info => do
    if Lean.isClass env name then
      let parents : List String :=
        match Lean.getStructureInfo? env name with
        | some info => (info.parentInfo.map (·.structName.toString)).toList
        | none => []
      IO.println <| jsonObject [
        jsonField "name" (toString name),
        jsonStrArrayField "parents" parents
      ]

end Wiggle

-- tactic to negate state, from Aristotle:
open Lean Meta Elab Tactic in
elab "revert_all" : tactic => do
  let goals ← getGoals
  let mut newGoals : List MVarId := []
  for mvarId in goals do
    newGoals := newGoals.append [(← mvarId.revertAll)]
  setGoals newGoals

open Lean.Elab.Tactic in
macro "negate_state" : tactic => `(tactic|
  (
    guard_goal_nums 1
    revert_all
    apply (by admit : ∀ {p : Prop}, ¬p → p)
    try (push Not; guard_goal_nums 1)
  )
)

-- Reverts only Prop-typed hypotheses, leaving type variables in context.
-- This lets contrapose! see a plain implication instead of a dependent ∀.
open Lean Meta Elab Tactic in
elab "revert_props" : tactic => do
  let goal ← getMainGoal
  let decl ← goal.getDecl
  let propFVars ← decl.lctx.foldlM (init := #[]) fun acc d => do
    if d.isImplementationDetail then return acc
    if ← isProp d.type then return acc.push d.fvarId
    else return acc
  let (_, newGoal) ← goal.revert propFVars (preserveOrder := true)
  replaceMainGoal [newGoal]

-- Tactic for getting the contrapositive of an implication
open Lean.Elab.Tactic in
macro "contrapositive" : tactic => `(tactic|
  (
    guard_goal_nums 1
    revert_props
    try (simp only [← and_imp])
    contrapose
    simp only [not_and_or, not_le, not_lt]
    guard_goal_nums 1
  )
)

-- Tactic for getting the converse of an implication
open Lean.Elab.Tactic in
macro "converse" : tactic => `(tactic|
  (
    guard_goal_nums 1
    revert_props
    try (simp only [← and_imp])
    apply (by admit : ∀ {p q : Prop}, (q → p) → (p → q))
    guard_goal_nums 1
  )
)

-- Tactic for getting the inverse of an implication: `P → Q` becomes `¬P → ¬Q`.
-- Logically equivalent to the converse (`¬P → ¬Q ↔ Q → P` by contrapositive),
-- and never to the original. Completes the classical foursome
-- {original, contrapositive, converse, inverse}.
open Lean.Elab.Tactic in
macro "inverse" : tactic => `(tactic|
  (
    guard_goal_nums 1
    revert_props
    try (simp only [← and_imp])
    apply (by admit : ∀ {p q : Prop}, (¬p → ¬q) → (p → q))
    guard_goal_nums 1
  )
)

-- De Morgan / connective rewriting via a fixed `simp only` lemma set.
-- Equivalence-preserving (truth unchanged from anchor). Returns the rewritten
-- statement via `extract_goal`. If `simp` makes no progress the Python wrapper
-- detects the no-op and emits no record.
--
-- Lemma set rationale:
--   not_and_or, not_or            -- De Morgan
--   not_forall, not_exists        -- quantifier De Morgan
--   imp_iff_not_or                -- material implication
--   and_imp                       -- curry / uncurry
--   not_not                       -- double negation elim
open Lean.Elab.Tactic in
macro "de_morgan_rewrite" : tactic => `(tactic|
  (
    guard_goal_nums 1
    revert_props
    simp only [not_and_or, not_or, not_forall, not_exists,
               imp_iff_not_or, and_imp, not_not]
    guard_goal_nums 1
  )
)


-- Curry: rewrite a conjunctive hypothesis `P ∧ Q → R` into `P → Q → R`.
-- Equivalence-preserving. Fires only when an explicit `∧` sits in hypothesis
-- position; otherwise `simp only` makes no progress and the macro fails (the
-- Python wrapper then emits no record).
open Lean.Elab.Tactic in
macro "curry" : tactic => `(tactic|
  (
    guard_goal_nums 1
    revert_props
    simp only [and_imp]
    guard_goal_nums 1
  )
)

-- Uncurry: rewrite `P → Q → R` into `(P ∧ Q) → R`. Equivalence-preserving.
-- The common case for Mathlib statements (which are usually curried).
open Lean.Elab.Tactic in
macro "uncurry" : tactic => `(tactic|
  (
    guard_goal_nums 1
    revert_props
    simp only [← and_imp]
    guard_goal_nums 1
  )
)

-- Definitional unfolding of common Mathlib predicates via `simp only [<def>]`.
-- Equivalence-preserving: turns e.g. `Function.Injective f` into
-- `∀ a b, f a = f b → a = b`, a syntactically very different but logically
-- identical statement (a strong positive pair for embedder training). Fails
-- (no record) when none of the listed predicates appear.
open Lean.Elab.Tactic in
macro "unfold_defs" : tactic => `(tactic|
  (
    guard_goal_nums 1
    simp only [Function.Injective, Function.Surjective, Function.Bijective,
               Function.LeftInverse, Function.RightInverse,
               Monotone, Antitone, StrictMono, StrictAnti]
    guard_goal_nums 1
  )
)

-- Removes Prop-valued hypotheses that are not used by the target or by later
-- hypotheses. This implements generalization by weakening hypotheses.
open Lean Meta Elab Tactic in
elab "clear_unused_props" : tactic => do
  let mut goal ← getMainGoal
  let decl ← goal.getDecl
  let fvars := decl.lctx.foldl (init := #[]) fun acc d =>
    if d.isImplementationDetail then acc else acc.push d.fvarId
  for fvarId in fvars.reverse do
    try
      let localDecl ← fvarId.getDecl
      if ← isProp localDecl.type then
        goal ← goal.clear fvarId
    catch _ =>
      pure ()
  replaceMainGoal [goal]

open Lean.Elab.Tactic in
macro "drop_unused_hyp" : tactic => `(tactic|
  (
    guard_goal_nums 1
    clear_unused_props
    guard_goal_nums 1
  )
)

open Lean Meta Elab Tactic Term in
def replaceMainGoalWithForExtraction (newTarget : Expr) : TacticM Unit := do
  let goal ← getMainGoal
  let oldTarget ← instantiateMVars (← goal.getType)
  let newGoal ← mkFreshExprMVarAt (← getLCtx) (← getLocalInstances)
    newTarget MetavarKind.syntheticOpaque (← goal.getTag)
  let bridgeType ← mkArrow newTarget oldTarget
  goal.assign (mkApp (← mkSorry bridgeType true) newGoal)
  replaceMainGoal [newGoal.mvarId!]

-- Adds a new Prop-valued assumption to the statement. The hypothesis is supplied
-- explicitly, because Lean cannot infer which stronger context you want.
open Lean Meta Elab Tactic Term in
elab "weaken_statement_by_strengthening_hypotheses " hyp:term : tactic => do
  liftMetaTactic1 fun goal => do
    goal.checkNotAssigned `weaken_statement_by_strengthening_hypotheses
    pure goal
  withMainContext do
    let oldTarget ← instantiateMVars (← getMainTarget)
    let hypType ← Term.elabType hyp
    replaceMainGoalWithForExtraction (← mkArrow hypType oldTarget)

-- Replaces the current conclusion with an explicitly supplied stronger target.
-- The caller is responsible for choosing a proposition that implies the original.
open Lean Meta Elab Tactic Term in
elab "strengthen_statement_by_strengthening_conclusion " newGoal:term : tactic => do
  liftMetaTactic1 fun goal => do
    goal.checkNotAssigned `strengthen_statement_by_strengthening_conclusion
    pure goal
  withMainContext do
    let newTarget ← Term.elabType newGoal
    replaceMainGoalWithForExtraction newTarget

-- Replaces the current conclusion with an explicitly supplied weaker target.
-- This is a statement-generation tactic: the admitted bridge lets extract_goal
-- print the requested perturbation while Python/Lean later checks compilation.
open Lean Meta Elab Tactic Term in
elab "weaken_statement_by_weakening_conclusion " newGoal:term : tactic => do
  liftMetaTactic1 fun goal => do
    goal.checkNotAssigned `weaken_statement_by_weakening_conclusion
    pure goal
  withMainContext do
    let newTarget ← Term.elabType newGoal
    replaceMainGoalWithForExtraction newTarget


-- `mutate_goal_type`: replaces `⊢ T` with `⊢ ∀ (h_extra : True), T`.
open Lean Meta Elab Tactic in
elab "mutate_goal_type" : tactic => do
  let g ← getMainGoal
  let decl ← g.getDecl
  let oldTy := decl.type
  -- Build: ∀ (h_extra : True), oldTy
  let newTy := mkForall `h_extra BinderInfo.default (mkConst ``True) oldTy
  -- Create a new metavariable with the mutated type
  let newGoal ← mkFreshExprMVar newTy
  replaceMainGoal [newGoal.mvarId!]


open Lean.Elab.Tactic in
macro "specialize_state" : tactic =>
  `(tactic|
    ( mutate_goal_type
      extract_goal
    )
  )
