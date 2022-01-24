#import json
import requests
import sys


def modrinth_search_mod (mod: str) -> str:
    payload = {
        "query": f"{mod}",
        "facets": "[ \
            [ \
                \"categories:fabric\" \
            ], \
            [ \
                \"versions:1.18\", \
                \"versions:1.18.1\" \
            ] \
        ]"
    }
    r = requests.get ("https://api.modrinth.com/api/v1/mod", params=payload)

    if r.status_code != 200:
        print (f"ERROR\n{r.text}")

    reply = r.json ()
    if reply["total_hits"] == 0:
        return None

    match = reply["hits"][0]
    return match["mod_id"]


def main() -> int:
    # FabricMC Installer.
    fmci_page_url = "https://meta.fabricmc.net/v2/versions/installer"
    print (f"Searching latest FabricMC Installer at {fmci_page_url}.")
    r = requests.get (fmci_page_url)

    # Check connection to FabricMC.
    if r.status_code != 200:
        print ("Could not connect to FabricMC meta repository. Exiting...")
        return 1
    print ("Successfully connected to FabricMC meta repository.")

    # Retrieve latest stable installer.
    fmci_file_url = None
    for obj in r.json ():
        if obj["stable"] is True:
            fmci_file_url = obj["url"]
            print (f"Latest fabric-installer stable version found is {obj['version']}.")
            break

    # Check connection to Modrinth.
    r = requests.get ("https://api.modrinth.com/")
    if r.status_code != 200:
        print ("Could not connect to Modrinth database. Exiting...")
        return 1
    print ("Successfully connected to Modrinth database.")

    # List of mods to retrieve
    core_mods = [
        "fabric-api",
        "ferritecore",
        "indium",
        "iris",
        "lambdynamiclights",
        "lithium",
        "modmenu",
        "sodium",
    ]

    for mod in core_mods:
        print (f"Searching for '{mod}'...", end='')
        mod_id = modrinth_search_mod (mod)
        if mod_id is None:
            print (f" FAIL")
        else:
            print (f" OK")


if __name__ == '__main__':
    sys.exit(main())  # next section explains the use of sys.exit
