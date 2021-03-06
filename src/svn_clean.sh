#!/bin/bash

# This script deletes all unversioned files in a working copy
# of subversion repository.

function list_unversioned_files {
	svn status --no-ignore | grep '^\?' | sed -e 's/\?\s*//g'
}

function svn_clean {
	list_unversioned_files | xargs rm -r
}

function main {
	list_unversioned_files

	while true; do
		read -p "All unversioned files will be deleted. Do you agree? [y/n]: " answer
		case $answer in
			[Yy]* ) svn_clean; exit;;
			[Nn]* ) exit;;
		esac
	done;
}

main

