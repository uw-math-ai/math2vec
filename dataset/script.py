import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
from urllib.parse import urlparse


BLUEPRINTS = [
    "https://leanprover-community.github.io/sphere-eversion/blueprint/dep_graph_document.html",
    "https://leanprover-community.github.io/liquid/dep_graph_section_1.html",
    "https://leanprover-community.github.io/liquid/dep_graph_section_2.html",
    "https://b-mehta.github.io/unit-fractions/blueprint/dep_graph_document.html",
    "https://leanprover-community.github.io/flt-regular/blueprint/dep_graph_document.html",
    "https://yaeldillies.github.io/LeanAPAP/blueprint/dep_graph_document.html",
    "https://teorth.github.io/pfr/blueprint/dep_graph_document.html",
    "https://remydegenne.github.io/testing-lower-bounds/blueprint/dep_graph_document.html",
    "https://pitmonticone.github.io/FLT3/blueprint/dep_graph_document.html",
    "https://imperialcollegelondon.github.io/FLT/blueprint/dep_graph_chapter_1.html",
    "https://imperialcollegelondon.github.io/FLT/blueprint/dep_graph_chapter_2.html",
    "https://imperialcollegelondon.github.io/FLT/blueprint/dep_graph_chapter_3.html",
    "https://imperialcollegelondon.github.io/FLT/blueprint/dep_graph_chapter_4.html",
    "https://imperialcollegelondon.github.io/FLT/blueprint/dep_graph_chapter_5.html",
    "https://imperialcollegelondon.github.io/FLT/blueprint/dep_graph_chapter_6.html",
    "https://imperialcollegelondon.github.io/FLT/blueprint/dep_graph_chapter_7.html",
    "https://imperialcollegelondon.github.io/FLT/blueprint/dep_graph_chapter_8.html",
    "https://imperialcollegelondon.github.io/FLT/blueprint/dep_graph_chapter_9.html",
    "https://imperialcollegelondon.github.io/FLT/blueprint/dep_graph_chapter_10.html",
    "https://imperialcollegelondon.github.io/FLT/blueprint/dep_graph_chapter_11.html",
    "https://imperialcollegelondon.github.io/FLT/blueprint/dep_graph_chapter_12.html",
    "https://imperialcollegelondon.github.io/FLT/blueprint/dep_graph_chapter_13.html",
    "https://imperialcollegelondon.github.io/FLT/blueprint/dep_graph_chapter_14.html",
    "https://florisvandoorn.com/carleson/blueprint/dep_graph_document.html",
    "https://emilyriehl.github.io/infinity-cosmos/blueprint/dep_graph_document.html",
    "https://teorth.github.io/equational_theories/blueprint/dep_graph_document.html",
    "https://thefundamentaltheor3m.github.io/Sphere-Packing-Lean/blueprint/dep_graph_document.html",
    "https://bergschaf.github.io/Localic-Caratheodory-Extensions/blueprint/dep_graph_chapter_1.html",
    "https://bergschaf.github.io/Localic-Caratheodory-Extensions/blueprint/dep_graph_chapter_2.html",
    "https://command-master.github.io/lean-bourgain/blueprint/dep_graph_document.html",
    "https://fredraj3.github.io/SemicircleLaw/blueprint/dep_graph_document.html",
    "https://leastauthority.github.io/STIR/blueprint/dep_graph_document.html",
    "https://remydegenne.github.io/CLT/blueprint/dep_graph_document.html",
    "https://remydegenne.github.io/brownian-motion/blueprint/dep_graph_document.html",
    "https://verified-zkevm.github.io/ArkLib/blueprint/dep_graph_chapter_1.html",
    "https://verified-zkevm.github.io/ArkLib/blueprint/dep_graph_chapter_2.html",
    "https://verified-zkevm.github.io/ArkLib/blueprint/dep_graph_chapter_3.html",
    "https://verified-zkevm.github.io/ArkLib/blueprint/dep_graph_chapter_4.html",
    "https://verified-zkevm.github.io/ArkLib/blueprint/dep_graph_chapter_5.html",
    "https://verified-zkevm.github.io/ArkLib/blueprint/dep_graph_chapter_6.html",
    "https://yaeldillies.github.io/ChandraFurstLipton/blueprint/dep_graph_document.html",
    "https://acmepjz.github.io/lean-iwasawa/blueprint/dep_graph_document.html",
    "https://b-mehta.github.io/ABC-Exceptions/blueprint/dep_graph_document.html",
    "https://florisvandoorn.com/BonnAnalysis/blueprint/dep_graph_document.html",
    "https://kkytola.github.io/ExtremeValueProject/blueprint/dep_graph_document.html",
    "https://firsching.ch/FormalBook/blueprint/dep_graph_document.html",
    "https://oliver-butterley.github.io/SpectralThm/blueprint/dep_graph_document.html",
    "https://thefundamentaltheor3m.github.io/Sphere-Packing-Lean/blueprint/dep_graph_document.html",
    "https://ilpreterosso.github.io/LEANearized-RadiiPolynomial/blueprint/dep_graph_document.html",
    "https://math-inc.github.io/strongpnt/blueprint/dep_graph_document.html",
    "https://alexkontorovich.github.io/PrimeNumberTheoremAnd/blueprint/dep_graph_document.html",
    "https://yaeldillies.github.io/toric/blueprint/dep_graph_document.html",
    "https://teorth.github.io/pfr/blueprint/dep_graph_document.html",
    "https://artie2000.github.io/real_closed_field/blueprint/dep_graph_document.html",
    "https://yaeldillies.github.io/LeanAPAP/blueprint/dep_graph_document.html",
    "https://emilyriehl.github.io/infinity-cosmos/blueprint/dep_graph_document.html",
    "https://bergschaf.github.io/lean-banach-tarski/blueprint/dep_graph_document.html",
    "https://remydegenne.github.io/testing-lower-bounds/blueprint/dep_graph_document.html",
    "https://kkytola.github.io/VirasoroProject/blueprint/dep_graph_document.html",
    "https://remydegenne.github.io/CLT/blueprint/dep_graph_document.html",
    "https://fredraj3.github.io/SemicircleLaw/blueprint/dep_graph_document.html",
    "https://riccardobrasca.github.io/Numbers/blueprint/dep_graph_document.html",
    "https://kkytola.github.io/ExtremeValueProject/blueprint/dep_graph_document.html"
]

OUTPUT_FILE = "blueprints.json"

blueprint_records = []

session = requests.Session()
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--blink-settings=imagesEnabled=false")
chrome_options.add_experimental_option(
    "prefs",
    {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
    },
)

try:
    driver = webdriver.Chrome(options=chrome_options)
except Exception as e:
    print(f"Error starting Chrome WebDriver: {e}")
    driver = None

try:
    for bp in BLUEPRINTS:
        try:
            response = session.get(bp)
        except requests.RequestException as e:
            print(f"Error fetching blueprint URL {bp}: {e}")
            continue
        if response.status_code != 200:
            print(f"Error fetching blueprint URL {bp}: status {response.status_code}")
            continue
        html_content = response.text

        # Convert the html_content into a soup (easily searchable and parsable document) and then parse it into thms/nodes
        soup = BeautifulSoup(html_content, "html.parser")
        thms = soup.select("div.thm[id]")
        if not thms:
            print(f"Error: no theorem nodes found for blueprint {bp}")
            continue

        records = []
        for n in thms:
            entry = {}
            entry["id"] = n["id"]

            thm_content = n.find("div", class_="thm_thmcontent")
            if not thm_content:
                print(f"Error: missing theorem content for id {n.get('id')}")
                continue
            entry["LaTeX"] = thm_content.get_text(strip=True)

            lean_a = n.select_one("a.lean_link.lean_decl")
            lean_url = lean_a["href"] if lean_a else None
            if not lean_url:
                print(f"Error: missing lean URL for id {n.get('id')}")
                continue
            lean_decl = lean_url.split("#doc/")[-1] if lean_url else None
            entry["lean_url"] = lean_url
            if not lean_decl:
                print(f"Error: missing lean declaration for id {n.get('id')}")
                continue
            entry["lean_decl"] = lean_decl

            if not driver:
                print("Error: WebDriver not available, skipping Selenium steps")
                break

            try:
                driver.get(lean_url)
            except Exception as e:
                print(f"Error loading lean URL {lean_url}: {e}")
                continue
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.ID, lean_decl))
                )
            except Exception as e:
                print(f"Error waiting for lean declaration {lean_decl} at {lean_url}: {e}")
                continue

            try:
                element = driver.find_element(By.ID, lean_decl)
            except Exception as e:
                print(f"Error finding lean declaration element {lean_decl} at {lean_url}: {e}")
                continue
            #print(element.get_attribute("outerHTML"))
            try:
                gh_link = element.find_element(By.CSS_SELECTOR, "div.gh_link a").get_attribute("href")
            except Exception as e:
                print(f"Error finding GitHub link for {lean_decl} at {lean_url}: {e}")
                continue
            if not gh_link:
                print(f"Error: empty GitHub link for {lean_decl} at {lean_url}")
                continue
            entry["gh_link"] = gh_link

            parsed = urlparse(gh_link)
            fragment = parsed.fragment
            match = re.search(r"L(\d+)(?:-L(\d+))?", fragment)
            if match:
                start_line = int(match.group(1))
                end_line = int(match.group(2) or match.group(1))
            else:
                print(f"Error: missing line fragment in GitHub URL {gh_link}")
                entry["highlighted"] = None
                records.append(entry)
                continue

            gh_path_match = re.match(
                r"https://github.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)",
                gh_link,
            )
            if not gh_path_match:
                print(f"Error: unexpected GitHub blob URL format {gh_link}")
                entry["highlighted"] = None
                records.append(entry)
                continue

            owner, repo, commit, path = gh_path_match.groups()
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{commit}/{path}"

            try:
                raw_resp = session.get(raw_url)
            except requests.RequestException as e:
                print(f"Error fetching raw GitHub file {raw_url}: {e}")
                entry["highlighted"] = None
                records.append(entry)
                continue
            if raw_resp.status_code != 200:
                print(f"Error fetching raw GitHub file {raw_url}: status {raw_resp.status_code}")
                entry["highlighted"] = None
                records.append(entry)
                continue

            raw_lines = raw_resp.text.splitlines()
            if start_line < 1 or end_line > len(raw_lines):
                print(
                    f"Error: line range {start_line}-{end_line} out of bounds for {raw_url} "
                    f"(file has {len(raw_lines)} lines)"
                )
                entry["highlighted"] = None
                records.append(entry)
                continue

            entry["highlighted"] = "\n".join(raw_lines[start_line - 1 : end_line])
            records.append(entry)

        blueprint_records.append(
            {
                "blueprint_url": bp,
                "theorems": records,
            }
        )
finally:
    if driver:
        driver.quit()

try:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as json_file:
        json.dump(blueprint_records, json_file, indent=2)
    print(f"Saved blueprint data to {OUTPUT_FILE}")
except IOError as e:
    print(f"Error saving file: {e}")


           





