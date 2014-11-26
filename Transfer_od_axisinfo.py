#!/usr/bin/python
import sys,re,os,string
import commands
import array
import math

from sepbase import *


def self_doc():
  print 

## This program will transfer the o and d information of the in.H header file 
#  Usage:    *.py out_inplace.H hdr=inHeader.H iAxes=3,4,5

eq_args,args=parse_args(sys.argv[1:])
fnameI	 = args[0] #assume the input file name is the first argument
fnameHdr = ""

if eq_args.has_key("hdr"):
	fnameHdr = eq_args["hdr"]
else:
	err("!!! need supply 'hdr' files")

iAxisList = []
if eq_args.has_key("iAxes"):
	iAxisList = eq_args["iAxes"].split(",")
else:
	err("!!! need supply 'iAxes' options")

str_iAxis = ""
print "list_iAxis=%s"%(iAxisList)

for str_iAxis in iAxisList:
	i_axis = int(str_iAxis)
	line1 = "In %s | grep n%1d= | awk '{$1=\"\"; print $0}' | xargs echo >> %s "%(fnameHdr,i_axis, fnameI)
	stat = os.system(line1)
	if (stat!=0):
		err("")
	
