#!/usr/bin/python
import sys,re,os,string
import commands
import array
import os
from sepbase import *

def self_doc():
  print 

## This program does preprocesing for a shY file, expand the #!include statements and create the corresponding sh file

# Usage1:    *.py my_pbs_script.shY my_pbs_script_out.sh
eq_args,args=parse_args(sys.argv[1:])
fn_in_script = args[0] #assume the input file name is the first argument
fn_out_script = args[1] #assume the target file name is the second argument

#separate the files and path
base_in = os.path.basename(fn_in_script); 	base_in_ext = os.path.splitext(base_in)[1]
base_out = os.path.basename(fn_out_script); 	base_out_ext = os.path.splitext(base_out)[1]

if base_in_ext != ".shY":
	print base_in,":",base_in_ext
	err("the input ext should be shY!")
if base_out_ext != ".sh":
	err("the output ext should be sh!")

#open the input & output file
fp_i = open(fn_in_script,'r'); fp_o = open(fn_out_script,'w')
line = ""
str_include = "#!include "
len_str_incl = len(str_include)
while 1:
	line = fp_i.readline();
	if not line:
		break
	else:	#copy the line unless there is a include statement, currently don't do recursive including
		if line[0:len_str_incl] != str_include:
			fp_o.write(line)
		else: #do the inclusion
			fn_incl = line.split(" ")[1]
			fp_incl = open(fn_incl,"r");
			lines_incl = fp_incl.readlines()
			fp_o.writelines(lines_incl);
			fp_incl.close()

fp_i.close();fp_o.close()

