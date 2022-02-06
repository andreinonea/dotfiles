#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import fnmatch
import os
import re
import sys
import winreg


def declare_task (msg: str):
    print (f"[RUN   ] {msg}")


def info_task (msg: str):
    print (f"[ INFO ] {msg}")


def finish_task (msg: str, success: bool=True) -> int:
    if success:
        print (f"[    OK] {msg}{os.linesep}")
        return 0
    else:
        print (f"[FAILED] {msg}{os.linesep}")
        input ("Press ENTER to exit...")
        return 1


# Thank you, 'unutbu', for this snippet.
# https://stackoverflow.com/questions/9129329/using-regex-in-python-to-get-episode-numbers-from-file-name
def get_episode_num_string (filename: str) -> str:
    match = re.search (
        r'''(?ix)                 # Ignore case (i), and use verbose regex (x)
        (?:                       # non-grouping pattern
          e|x|episode|^           # e or x or episode or start of a line
          )                       # end non-grouping pattern 
        \s*                       # 0-or-more whitespaces
        (\d{2})                   # exactly 2 digits
        ''', filename)
    if match:
        return match.group (1)


# Thank you, 'Smitha Dinesh Semwal', for this snippet.
# https://www.geeksforgeeks.org/python-split-camelcase-string-to-individual-strings/
def split_camel_case (filename: str):
    return re.findall (r'[A-Z](?:[a-z]+|[A-Z]*(?=[A-Z]|$))', filename)


# TODO: Have a function here to fill out any missing version numbers


def main (args: argparse.Namespace) -> int:
    if args.should_install:
        try:
            declare_task ("Installing Windows registry key...")
            key_path = rf"Directory\\Background\\shell\\md-formatter"
            key = winreg.CreateKeyEx (winreg.HKEY_CLASSES_ROOT, key_path, access=winreg.KEY_SET_VALUE)
            cmd_key = winreg.CreateKeyEx (key, r"command", access=winreg.KEY_SET_VALUE)
            winreg.SetValue (key, '', winreg.REG_SZ, "Format media directory...")
            winreg.SetValue (cmd_key, '', winreg.REG_SZ, f"{sys.executable} {os.path.realpath(__file__)}")
            return finish_task ("Registry key added.")
        except PermissionError as perror:
            return finish_task ("You need administrator rights to access the registry.", success=False)
        except Exception as exception:
            return finish_task (f"unexpected error occured: {exception}", success=False)
        
    if args.should_remove:
        try:
            declare_task ("Removing Windows registry key...")
            key_path = rf"Directory\\Background\\shell\\md-formatter"
            winreg.DeleteKeyEx (winreg.HKEY_CLASSES_ROOT, rf"{key_path}\\command", access=winreg.KEY_SET_VALUE)
            winreg.DeleteKeyEx (winreg.HKEY_CLASSES_ROOT, key_path, access=winreg.KEY_SET_VALUE)
            return finish_task ("Registry key removed.")
        except PermissionError as perror:
            return finish_task ("You need administrator rights to access the registry "
                "or the key does not exist.", success=False)
        except Exception as exception:
            return finish_task (f"unexpected error occured: {exception}", success=False)

    declare_task (f"Renaming files in {os.getcwd ()}")
    basetitle = input (f"Hint: it must resemble at least one word of the original filenames{os.linesep}"
        "Enter new basename for all files to be renamed: ")
    filelist = []
    for filename in os.listdir (os.getcwd ()):
        if os.path.isfile (filename):
            filelist.append (filename)
    if not filelist:
        return finish_task (f"Directory does not contain any files.", success=False)

    # Attempt to match using the basetitle itself.
    matches = fnmatch.filter (filelist, f"*{basetitle}*")

    if not matches:
        # Attempt to match using any of the words in the basetitle.
        for word in basetitle.split ():
            matches = fnmatch.filter (filelist, f"*{word}*")
            if matches:
                break
    if not matches:
        # Attempt to split the basetitle by any of ['.', '_', '-'] and match using any of the words.
        found = False
        for delimiter in ['.', '_', '-']:
            for word in basetitle.split (delimiter):
                matches = fnmatch.filter (filelist, f"*{word}*")
                if matches:
                    found = True
                    break
            if found:
                break
    if not matches:
        # Attempt to split the basetitle by CamelCase and match using any of the words.
        for word in split_camel_case (basetitle):
            matches = fnmatch.filter (filelist, f"*{word}*")
            if matches:
                break
    if not matches:
        return finish_task (f"No files could be detected from basename '{basetitle}'.", success=False)

    changes = []
    should_rename = True
    for filename in matches:
        ext = os.path.splitext (filename)[1]
        ep_num_string = get_episode_num_string (filename)
        new_filename = f"{basetitle}E{ep_num_string}{ext}"
        if not ep_num_string:
            new_filename = None
        changes.append ([filename, new_filename])  
    
    if args.should_confirm:
        info_task ("The following files will be renamed:")
        for change in changes:
            if not change[1]:
                print (f"    {change[0]} will be skiped: no episode number detected")
            else:
                print (f"    {change[0]} -> {change[1]}")

        choice = input ("Keep changes? (y/N): ")
        if choice != "yes" and choice != "y":
            declare_task ("Reverting changes...")
            finish_task ("Original filenames have been kept.")
            should_rename = False

    if should_rename:
        declare_task ("Applying changes...")
        for change in changes:
            if not change[1]:
                continue
            os.rename (change[0], change[1])
        finish_task ("Files have been renamed.")

    input ("Press ENTER to exit...")
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Renames all matching media files with given format.")
    parser.add_argument ("-i", "--install",
        dest="should_install",
        action="store_true",
        default=False,
        help="install Windows registry key for context menu option")
    parser.add_argument ("-r", "--remove",
        dest="should_remove",
        action="store_true",
        default=False,
        help="remove Windows registry key for context menu option")
    parser.add_argument ("-f", "--force",
        dest="should_confirm",
        action="store_false",
        default=True,
        help="rename files without asking for confirmation")

    # Only available on Windows for now.
    args = parser.parse_args ()
    if sys.platform == "win32":
        sys.exit (main (args))

    print ("Program is only available on Windows at the moment :(.")
    sys.exit (0)
