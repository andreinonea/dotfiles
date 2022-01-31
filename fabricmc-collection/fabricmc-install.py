#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import requests
import subprocess
import sys
from tempfile import NamedTemporaryFile

# download_file function inspired from Roman Podlinov
# and adapted to suit our use cases.
# https://stackoverflow.com/questions/16694907/download-large-file-in-python-with-requests

program_name = "FabricMC Installer"
program_version = "v0.1"
program_author = "Andrei N. Onea"


class Configuration:
  def __init__(self, mods_list, custom_loader_version, custom_minecraft_version, use_snapshots):
    self.mods_list = mods_list
    self.custom_loader_version = custom_loader_version
    self.custom_minecraft_version = custom_minecraft_version
    self.use_snapshots = use_snapshots


# Parse a configuration FILE argument.
# For the moment works with exact versions.
# Maybe some day it will work with >=
# or it will have proper dependencies...
def validate_config_file(path: str) -> str:
    print (path)
    try:
        file = open (path, 'r')

        mods_list = []
        custom_loader_version = None
        custom_minecraft_version = None
        use_snapshots = False

        for line in file:
            if line.startswith("#"):
                continue
            pair = line.split ('=', maxsplit=1)
            if pair[0] == "minecraft":
                custom_minecraft_version = pair[1]
                if pair[1].find ('w') != -1: # snapshot version
                    use_snapshots = True
            if pair[0] == "fabric-loader":
                custom_loader_version = pair[1]
            pair[1] = pair[1].strip() # Strip \n on Windows
            mods_list.append (pair)

        if not mods_list:
            raise Exception ("mods list is empty")

        return Configuration (mods_list, custom_loader_version, custom_minecraft_version, use_snapshots)

    except Exception as err:
        raise argparse.ArgumentTypeError(f"path does not lead to a valid configuration\nmessage: {err}.")


def modrinth_search_mod (mod: str) -> str:
    payload = {
        "query": f"{mod}",
        "facets": f"[ \
            [ \
                \"categories:fabric\" \
            ] \
        ]"
    }
    r = requests.get ("https://api.modrinth.com/api/v1/mod", params=payload)

    if r.status_code != 200:
        print (f"ERROR\n{r.text}")

    reply = r.json ()
    if reply["total_hits"] == 0:
        return None

    return reply["hits"][0]


def main(configuration: Configuration) -> int:
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

    # Download and install Fabric Client.
    with requests.get (fmci_file_url, stream=True) as r:
        r.raise_for_status ()
        file_size = len (r.content)
        with NamedTemporaryFile(delete=False) as fd:
            for chunk in r.iter_content (chunk_size=8192):
                fd.write (chunk)
            fd.close ()
            if file_size != os.path.getsize (fd.name):
                print (f" FAIL\nIntegrity of the installer could not be verified.")
                return 2
            print (f"Downloaded {fmci_file_url.split ('/')[-1]}")

            print ("Beginning installation...")

            cmd = f'java -jar {fd.name} client -dir "{mc_dir}"'
            if configuration.use_snapshots:
                cmd += f' -snapshot'
            if configuration.custom_loader_version:
                cmd += f' -loader {configuration.custom_loader_version}'
            if configuration.custom_minecraft_version:
                cmd += f' -mcversion {configuration.custom_minecraft_version}'

            result = subprocess.run (cmd, shell=True, capture_output=True, universal_newlines=True)
            print (result.stdout)
            if result.stdout.find ("Done") == -1: # stupid way to check for success...
                print (f"Could not properly install Fabric Client. Exiting...")

            os.unlink (fd.name)

    # Above: all things related to Fabric Installer
    # Below: all things related to mods. Using lowest compatibility version 1.18.

    # Make sure 'mods' directory exists in Minecraft folder
    if not os.path.exists(mods_dir):
        os.makedirs(mods_dir)
        print ("Created 'mods' directory.")

    # Check connection to Modrinth.
    r = requests.get ("https://api.modrinth.com/")
    if r.status_code != 200:
        print ("Could not connect to Modrinth database. Exiting...")
        return 1
    print ("Successfully connected to Modrinth database.")

    # Struct containing information about the mods which will be installed
    # [0] title
    # [1] download_url
    to_be_installed = []

    mods_invalid = []
    mods_version_mismatched = []
    mods_couldnt_download = []

    for mod_info in configuration.mods_list:
        print (f"Searching for '{mod_info[0]}'...", end='')
        mod = modrinth_search_mod (mod_info[0])
        if mod is None:
            print (f" FAIL")
            mods_invalid.append (mod_info[0])
        else:
            # remove "local-" from id name
            mod_id = mod["mod_id"].split ('-')[-1]
            mod_title = mod["title"]
            mod_version = mod_info[1]

            # Get download link
            found = False
            r = requests.get (f"https://api.modrinth.com/api/v1/mod/{mod_id}/version")
            for candidate in r.json ():
                if candidate["version_number"] == mod_version:
                    print (" OK")
                    found = True
                    mod_url = candidate['files'][0]['url']
                    to_be_installed.append ([mod_title, mod_url])

            if not found:
                print (f" FAIL\n[{mod_title}] Could not find release candidate for version {mod_version}.")
                mods_version_mismatched.append ([mod_title, mod_version])

    for mod_info in to_be_installed:
        # Add jar file to mods folder
        url = mod_info[1]
        filename = url.split ('/')[-1]
        path = os.path.join (mods_dir, filename)

        print (f"[{mod_info[0]}] Downloading and copying over mod...", end='')
        with requests.get (url, stream=True) as r:
            r.raise_for_status ()
            file_size = len (r.content)
            with open (path, 'wb') as fd:
                for chunk in r.iter_content (chunk_size=8192):
                    fd.write (chunk)
            if file_size != os.path.getsize (path):
                print (f" FAIL\n[{mod_info[0]}] Integrity of file could not be verified.")
                mods_couldnt_download.append (mod_info[0])

        print (" OK")
        print (f"[{mod_info[0]}] Successfully installed at {path}.")

    not_downloaded_count = len (mods_couldnt_download)
    installed_count = len (to_be_installed) - not_downloaded_count
    print (f"Summary: {installed_count} mods successfuly installed")
    if not_downloaded_count:
        print (f"         {not_downloaded_count} mods could not be downloaded")
        for mod_title in mods_couldnt_download:
            print (f"             {mod_title}")
    if mods_version_mismatched:
        print (f"         {len (mods_version_mismatched)} mods have invalid version")
        for mod_info in mods_version_mismatched:
            print (f"             {mod_info[0]}: {mod_info[1]}")
    if mods_invalid:
        print (f"         {len (mods_invalid)} mods could not be found by their identifiers")
        for mod_id in mods_invalid:
            print (f"             {mod_id}")

if __name__ == '__main__':

    # Use default Minecraft path for both platforms
    mc_dir = ""
    if sys.platform == "win32":
        mc_dir = os.path.join(os.getenv('APPDATA'), '.minecraft')
    else:
        mc_dir = os.path.expanduser ('~/.minecraft')
    mods_dir = os.path.join (mc_dir, "mods")
    default_config_path = os.path.join (mc_dir, ".fabric_config")

    parser = argparse.ArgumentParser(description=f"""
        {program_name} {program_version}{os.linesep}
        Copyright (C) 2021 {program_author}
        Utility script that installs Fabric Loader and mods found in a config file.
    """)

    parser.add_argument ("--file", metavar="CONFIGURATION", type=validate_config_file, default=default_config_path,
        help="""path to the configuration file holding the mods --
                Fabric Loader must be the first.""")
    args = parser.parse_args ()

    sys.exit(main(args.file))
