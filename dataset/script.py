import json
import requests     
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time


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

        # this is just to limit the thms for testing purposes 
        # TODO: Remove Later 
        thms = [thms[0]]


        records = []
        for n in thms: 
            entry = {}
            entry["id"] = n["id"]
            heading = n.select_one("div.thm_thmheading")

            cap = heading.select_one('span[class$="_thmcaption"]')
            kind = cap.get_text(strip=True).lower() if cap else None 
            entry["kind"] = kind

            content = n.find("div", class_="thm_thmcontent").get_text(strip=True)
            entry["LaTeX"] = content

            lean_a = n.select_one("a.lean_link.lean_decl")
            lean_url = lean_a["href"] if lean_a else None
            lean_decl = lean_url.split("#doc/")[-1] if lean_url else None
            entry["lean_link"] = lean_url
            entry["lean_decl"] = lean_decl
            
            # We need to use a headless browser to acess the lean_url and then acess the lean code and save it in the dict
            driver= webdriver.Chrome()
            
            driver.get(lean_url)
            time.sleep(10)

            if lean_decl:
                print(lean_decl)
                element = driver.find_element(By.ID, lean_decl)
                #print(element.get_attribute("outerHTML"))
                gh_link = element.find_element(By.CSS_SELECTOR, "div.gh_link a")
                print(gh_link.get_attribute("href"))
                github_response = requests.get(gh_link)
                print(github_response)

            # WebDriverWait(driver, 100).until(
            #     EC.presence_of_element_located((By.TAG_NAME, "body"))
            # )

            # WebDriverWait(driver, 10).until(
            #     lambda d: d.execute_script("return document.readyState") == "complete"
            # )


            records.append(entry)


        




        # filename = 'bp.json'
        # try:
        #     with open(filename, 'w') as json_file:
        #         json.dump(records, json_file, indent=4)
        #         print(f"Successfully saved dictionary to {filename}")
        # except IOError as e:
        #      print(f"Error saving file: {e}")


           





