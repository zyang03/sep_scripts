#!/usr/bin/python
import sys,re,os,string
import commands
import array
import os
from sepbase import *

def self_doc():
  print 
  print 
  print 
  print 
  print 

## This program make tarball files from the report folders (with reproduciblilty files) under vostok:/wrk/, and copy them to /web/html/data/private/docs/sep152/ to publish them on web

# Usage1:    *.py fnlist.txt wrk_folder=[sep152rep] web_folder=[sep152] oper=[1,2]
# oper=1, create tarballs. tar -cvzf 
# oper=2, mv the tarballs to the web folder

eq_args,args=parse_args(sys.argv[1:])
fn_list = args[0] #assume the input file name is the first argument

wrk_folder = ""; web_folder = ""; oper=0

if eq_args.has_key("wrk_folder"):
	wrk_folder = eq_args["wrk_folder"]
else:
	err("need wrk_folder= !")
if eq_args.has_key("web_folder"):
	web_folder = eq_args["web_folder"]
else:
	err("need web_folder= !")
if eq_args.has_key("oper"):
	oper = eq_args["oper"]
else:
	err("need oper= !")

wrk_folder = "/wrk/"+wrk_folder
web_folder = "/net/zapad//web/html/data/media/private/docs/"+web_folder
print "wrk_folder=",wrk_folder," ","web_folder=",web_folder

#open the input file list
fp_i = open(fn_list,'r') 
line = ""; cmd=""
while 1:
	line = fp_i.readline();
	line = line.rstrip('\n')
	if not line:
		break
	else:	# fetch the file name for each line
		if line[0:1] == "#": #skip this line
			continue
		else: #do the file
			fname = line
			#wrk_folder_idv = wrk_folder+"/"+fname
			wrk_folder_idv = fname
			web_folder_idv = web_folder+"/"+fname
			tarball_idv = wrk_folder+"/"+fname+".tar.gz"
			#print "%s;%s;%s"%(wrk_folder_idv,web_folder_idv,tarball_idv)
			if oper=="1":
				cmd = "tar -cvzf %s %s"%(tarball_idv,wrk_folder_idv)
			elif oper=="2":
				cmd = "cp %s %s"%(tarball_idv,web_folder_idv)
			else:
				err("oper option must be 1 or 2!")
			print "cmd=%s"%(cmd)
			#stat2,out2=commands.getstatusoutput(cmd)
			os.system(cmd)
fp_i.close()

