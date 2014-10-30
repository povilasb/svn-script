#!/usr/bin/python

import os
import sys
import subprocess
from optparse import OptionParser

import svn_utils
import console_utils


#
# Returns exit code.
#
def main():
	retval = 0

	opt_parser = OptionParser()
	(options, args) = opt_parser.parse_args();

	if len(args) > 0:
		svn_flow = SvnFlow()

		cmd = args[0]
		if cmd == "init":
			svn_flow.init()

		elif cmd == "test":
			retval = svn_flow.test()

		elif cmd == "feature":
			on_cmd_feature(svn_flow, args[1:])

		else:
			retval = 1
			console_utils.print_error("Unknown command: " + cmd)
	else:
		print "Usage:"
		print ("\tsvn-flow init - initializes svn repository to work "
			"with svn-flow.")

	return retval


def on_cmd_feature(svn_flow, args):
	if len(args) < 1:
		cmd = "help"
	else:
		cmd = args[0]

	if cmd == "start":
		# TODO: check if args[1] a.k.a feature name is specified.
		svn_flow.feature_start(args[1])

	elif cmd == "finish":
		svn_flow.feature_finish(args[1])

	elif cmd == "list":
		pass
		# TODO

	elif cmd == "help":
		on_cmd_feature_help()

	else:
		console_utils.print_error("Unknown command: " + cmd)
		on_cmd_feature_help()


def on_cmd_feature_help():
	print "Usage:"
	print ("\tsvn-flow feature start <name> - creates new branch off "
		"develop named branches/feature/<name>.")
	print ("\tsvn-flow feature finish <name> - merges branches/feature<name> "
		"back to develop.")


def log(msg):
	print msg


class Svn:
	def __init__(self, svn_root_path):
		self.root_path = svn_root_path

	#
	# The specified directory path is relative to svn repository root path.
	# E.g. to create trunk directory simply execute
	#	svn.mkdir("trunk")
	#
	def mkdir(self, relative_dir_path):
		full_path = os.path.join(self.root_path, relative_dir_path)
		subprocess.call(["svn", "mkdir", full_path])

	def commit(self, msg):
		subprocess.call(["svn", "commit", "-m", msg])

	#
	# The specified directory paths are relative to svn repository root path.
	# E.g. to create development branch directory simply execute
	#	svn.branch("trunk", "branches/develop")
	#
	def branch(self, src_dir, target_dir):
		src_dir = os.path.join(self.root_path, src_dir)
		target_dir = os.path.join(self.root_path, target_dir)
		subprocess.call(["svn", "copy", src_dir, target_dir])

	#
	# Calls svn update on repository root path: recursively updates
	# all branches.
	#
	def update_all(self):
		subprocess.call(["svn", "update", self.root_path])

	#
	# Returns list of directories and files added to svn
	# repo that are in the specified directory. This directory path
	# is relative to svn repo root path. Default value is svn repo root
	# path.
	#
	def list(self, dir = ""):
		full_path = os.path.join(self.root_path, dir)

		output = subprocess.check_output(["svn", "list", full_path])
		lines = output.split("\n")
		lines.remove("")

		return lines

	#
	# Returns True if the specified path is tracked by svn. False otherwise.
	#
	def is_tracked(self, file_path):
		full_path = os.path.join(self.root_path, file_path)

		fnull = open(os.devnull, "w")
		svn_retval = subprocess.call(["svn", "info", full_path], \
			stdout = fnull, stderr = fnull)
		return not bool(svn_retval)

	#
	# Returns full system path to the specified path relative to repository
	# root path.
	#
	def full_path(self, path):
		return os.path.join(self.root_path, path)


	def merge(self, src_dir, dest_dir, reintegrate = False):
		os.chdir(self.full_path(dest_dir))

		args = ["svn", "merge"]
		if reintegrate:
			args.append("--reintegrate")

		args.append(self.full_path(src_dir))
		subprocess.call(args)


class SvnFlow:
	def __init__(self):
		self.svn = Svn(svn_utils.find_svn_root_path())
		self.branches_dir = "branches"
		self.develop_branch = os.path.join(self.branches_dir, "develop")
		self.features_dir = os.path.join(self.branches_dir, "feature")


	def init(self):
		self.__create_dir("trunk")

		branches_dir = "branches"
		self.__create_dir(branches_dir)

		self.__create_dir("tags")

		self.__create_develop_branch(branches_dir)

		features_dir = os.path.join(branches_dir, "feature")
		self.__create_dir(features_dir)

		releases_dir = os.path.join(branches_dir, "release")
		self.__create_dir(releases_dir)

		hotfix_dir = os.path.join(branches_dir, "hotfix")
		self.__create_dir(hotfix_dir)

		self.svn.update_all()


	#
	# Returns 0 if no errors were encountered. Otherwise 1 is returned.
	#
	def test(self):
		retval = 0

		retval = retval or self.__test_dir("trunk")
		retval = retval or self.__test_dir("tags")

		branches_dir = "branches"
		retval = retval or self.__test_dir(branches_dir)

		retval = self.__test_branches_subdir(branches_dir, "feature") \
			or retval
		retval = self.__test_branches_subdir(branches_dir, "release") \
			or retval
		retval = self.__test_branches_subdir(branches_dir, "hotfix") \
			or retval

		return retval


	def feature_start(self, name):
		feature_branch = os.path.join(self.features_dir, name)
		if os.path.exists(self.svn.full_path(feature_branch)):
			raise Exception("Feature branch '" + feature_branch \
				+ "' already exists.")

		self.svn.update_all()
		self.svn.branch(self.develop_branch, feature_branch)
		self.__commit_and_log("Created feature branch '" + name + "'.");
		self.svn.update_all()


	def feature_finish(self, name):
		feature_branch = os.path.join(self.features_dir, name)
		self.__raise_if_dir_invalid(feature_branch)

		self.svn.update_all()
		self.svn.merge(feature_branch, self.develop_branch)
		self.__commit_and_log("Merged feature '" + name + "' to develop.")
		self.svn.update_all()


	def __test_branches_subdir(self, branches_dir, subdir):
		branches_subdir = os.path.join(branches_dir, subdir)
		return self.__test_dir(branches_subdir)


	def __test_dir(self, dir_path):
		retval = 0

		try:
			self.__raise_if_dir_invalid(dir_path)
			self.__raise_if_not_exists(dir_path)

			log(dir_path + " [" + console_utils.text_green("OK") +"]")
		except Exception, e:
			log(dir_path +" [" + console_utils.text_red("FAIL") +"]")
			console_utils.print_error(str(e))
			retval = 1

		return retval


	def __create_dir(self, dir_path):
		self.__raise_if_dir_invalid(dir_path)

		full_path = os.path.join(self.svn.root_path, dir_path)
		if not os.path.exists(full_path):
			self.svn.mkdir(dir_path)
			self.__commit_and_log("Created directory '" \
				+ dir_path + "'.")
		else:
			log("Directory '" + dir_path + "' exists. Skipping.")


	def __create_develop_branch(self, branches_dir):
		dir_path = os.path.join(branches_dir, "develop")
		self.__raise_if_dir_invalid(dir_path)

		full_path = os.path.join(self.svn.root_path, dir_path)
		if not os.path.exists(full_path):
			self.svn.branch("trunk", dir_path)
			self.__commit_and_log("Created 'develop' branch.")
		else:
			log("Branch 'develop' exists. Skipping")


	def __commit_and_log(self, msg):
		self.svn.commit(msg)
		log(msg)


	def __raise_if_dir_invalid(self, dir_path):
		full_path = os.path.join(self.svn.root_path, dir_path)

		if os.path.exists(full_path) and not self.svn.is_tracked(dir_path):
			raise Exception("'" + dir_path + "' is not tracked by SVN.")

		if self.svn.is_tracked(dir_path) and not os.path.isdir(full_path):
			raise Exception("'" + dir_path + "' is not a directory.")


	def __raise_if_not_exists(self, path):
		full_path = os.path.join(self.svn.root_path, path)
		if not os.path.exists(full_path):
			raise Exception("'" + full_path + "' does not exist.")


exit(main())
