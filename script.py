import json
import requests     
from bs4 import BeautifulSoup


BLUEPRINTS = [
   "https://leanprover-community.github.io/sphere-eversion/blueprint/dep_graph_document.html"
]

for bp in BLUEPRINTS:
    response = requests.get(bp)
    if response.status_code == 200:
        html_content = response.text
        

        # Convert the html_content into a soup (easily searchable and parsable document) and then parse it into thms/nodes
        soup = BeautifulSoup(html_content, "html.parser")
        thms = soup.select("div.thm[id]")

        thms = [thms[0]]


        records = []
        for n in thms: 
            entry = {}
            entry["id"] = n["id"]

            content = n.find("div", class_="thm_thmcontent").get_text(strip=True)
            entry["LaTeX"] = content

            lean_a = n.select_one("a.lean_link.lean_decl")
            lean_url = lean_a["href"] if lean_a else None
            lean_decl = lean_url.split("#doc/")[-1] if lean_url else None
            entry["lean_link"] = lean_url
            entry["lean_decl"] = lean_decl
            
            # We need to use a headless browser to acess the lean_url and then acess the lean code and save it in the dict


            records.append(entry)


        




        # filename = 'bp.json'
        # try:
        #     with open(filename, 'w') as json_file:
        #         json.dump(records, json_file, indent=4)
        #         print(f"Successfully saved dictionary to {filename}")
        # except IOError as e:
        #      print(f"Error saving file: {e}")


           





