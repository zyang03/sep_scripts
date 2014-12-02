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

## This program fills in the unfinished shots given a finished shots list
# Usage1:    *.py shotlist shotlist.redolist N=tot_num_files

eq_args,args=parse_args(sys.argv[1:])
fn_in_script = args[0] #assume the input file name is the first argument
fn_out_script = args[1] #assume the target file name is the second argument

#separate the files and path
if eq_args.has_key("N"):
	N=int(eq_args["N"])
else:
	assert False, "!Warning: Not specifying N!"

j = 1
if eq_args.has_key("j"):
	n=int(eq_args["j"])
else:
	print ("!Warning: Not specifying j, use j=1")

#open the input & output file
fp_i = open(fn_in_script,'r'); fp_o = open(fn_out_script,'w')
line = ""
ishot_beg = 0
while 1:
	line = fp_i.readline();
	if not line:
		break
	else:	#copy the line unless there is a include statement, currently don't do recursive including
		ishot = int(line)
		for j in range(ishot_beg,ishot):
			fp_o.write("%d\n"%j)
		ishot_beg = ishot+1

#do the last one
for j in range(ishot_beg,N):
	fp_o.write("%d\n"%j)

fp_i.close();fp_o.close()

