#!/usr/bin/python
import sys,re,os,string
import commands
import array
import math

from sepbase import *


def self_doc():
  print 

## This program will convert the unit in the .H file dimensions, basically for better plotting
# Usage:    *.py in.H out.H scale=0.001,0.001,0.001

eq_args,args=parse_args(sys.argv[1:])
fnameI = args[0] #assume the input file name is the first argument
fnameO = args[1] 

his_grid = {}
his_eachshot={}
get_sep_grid_params(fnameI,his_grid,'g')

print eq_args,"\n"
print "\n", his_grid,"\n"

#figureout the output shotsInfo file name
ndim = 1
n_os = [0.,0.,0.,0.,0.,0.]
n_ds = [1.,1.,1.,1.,1.,1.]
n_sc = [1.,1.,1.,1.,1.,1.]

if eq_args.has_key("scale"):
  str_list=eq_args["scale"].split(",")
  ndim = len(str_list)
  print ndim,str_list
  #and then make sure each dimension is supplied with a scaler
  for i in range(ndim,6,1):
    n = int(his_grid["ng_%1d"%(i+1)])
    if (n!=1):
      err("Need more scale coefficient for all non-trivial axis!")
else:
  err("specify scale!!!")

#first cp the header
cmd1 = "cp %s %s"%(fnameI, fnameO)
RunShellCmd(cmd1)

print "ndim=%d"%ndim
fp_o = open(fnameO,"a")
fp_o.write("\n")
for idim in range(0,ndim,1):
  sc = float(str_list[idim])
  n_os[idim] = float(his_grid["og_%1d"%(idim+1)]) * sc
  n_ds[idim] = float(his_grid["dg_%1d"%(idim+1)]) * sc
  line1 = "o%1d=%.5f d%1d=%.5f "%(idim+1,n_os[idim],idim+1,n_ds[idim])
  print line1
  #if (math.fabs(sc-0.001)<1e-6):
  #  line1 += "label%1d=%s "%(idim+1,"k"+his_grid["labelg_%1d"%(idim+1)])
  fp_o.write(line1+"\n")

fp_o.close()

