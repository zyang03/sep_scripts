#!/usr/bin/python
import sys,re,os,string
import commands
import array
from sepbase import *


def self_doc():
  print 
  print 
  print 
  print 
  print 

## This program will try to Window3d a big sep-3d data file into small pieces, do someprocessing and finally convert each piece to an individual sep77 files, usage
# *.py ../gthnomigdem_grid3d_2.H oper=gen_c path=data_header_path

eq_args,args=parse_args(sys.argv[1:])

## Need to have oper= option specified, otherwise don't know what operation to do
oper = ""
if eq_args.has_key("oper"):
	oper = eq_args["oper"]

if (oper=="") or not (oper in ["gen_c","verify","remotecp"]) :
	print "oper= is missing!! , need to Specify oper = gen_c,verify,remotecp"
	exit(-1)

fname = args[0] #assume the target file name is the first argument
his_3d = {}
his_grid = {}
get_sep_params(fname,his_3d,'g')
get_sep_grid_params(fname,his_grid,'g')

print eq_args,"\n"
print "\n", his_3d,"\n"
print "\n", his_grid,"\n"

# axis 5 and 6 are the shot_x and shot_y axis, we should divide the data domain into small, for now, just do 2 by 2 blocks.
n5 = int(his_grid["ng_5"]); n6 = int(his_grid["ng_6"])
o5=0
#test
#n5=2; n6=1

o5=4;n5=178;j5=2 #
n6=21;o6=1;j6=1
n5 = int(his_grid["ng_5"]); n6 = int(his_grid["ng_6"])
o5 = 0; o6 = 0
if eq_args.has_key("beg5"):
	o5 = int(eq_args["beg5"])
if eq_args.has_key("beg6"):
	o6 = int(eq_args["beg6"])
if eq_args.has_key("end5"):
	n5 = int(eq_args["end5"])
if eq_args.has_key("end6"):
	n6 = int(eq_args["end6"])
res5 = (n5-o5)%j5; res6 = (n6-o6)%j6

cmd1 = ""; cmd2=""; cmd3=""; cmd4=""; cmd5=""; cmd6=""
n6_wnd = j6

base = os.path.basename(fname); base_wo_ext = os.path.splitext(base)[0]
fname_out = ""; fname_out2=""; path_out = ""; fname_out2_base=""
if eq_args.has_key("path"):
	path_out = eq_args["path"]
else:
	path_out = "."

bin_tang = "/homes/sep/yang/from-other/yaxun_weo/bin"
bin_Y = "/net/server/yang/bin"
#extract the input's name, append the iy_ix info to the filename, and then append .H to it

for iy in range(o6,n6,j6):
	if (iy == n6-res6): #if it is the last block
		n6_wnd = res6
	n5_wnd = j5
	for ix in range(o5,n5,j5):
		if (ix == n5-res5): #if it is the last block
			n5_wnd = res5
		fname_out = "%s/%s_%02d_%03d.H"%(path_out,base_wo_ext,iy,ix)
		fname_out2_base = "%s_%02d_%03d_c.H"%(base_wo_ext,iy,ix)
		fname_out2 = "%s/%s"%(path_out,fname_out2_base)
		if (oper=="gen_c"):
			#window the data into small blocks.
			cmd1 = "Window3d <%s f5=%d f6=%d n5=%d n6=%d >%s hff=%s@@ gff=%s@@@@ "%(fname,ix,iy,n5_wnd,n6_wnd,fname_out,fname_out,fname_out)
			#after this, do a infill3d, and then do wei_transf.x to convert it to frequency domain
			cmd2 = "Infill3d axes=2 normalize=y <%s  | Window3d n1=1536 j1=2 > t.H"%(fname_out)
			
			# Do the muting and marine gain to the data
			cmd3 = "<t.H %s/Mute.x WB_tt=../WB_tt-velmod_asb3_rev_pwave-waz3d.H b3D=1 vmute=1500 tmute=-0.16 offset=y bDoMGain=1 >t2.H"%(bin_Y)
			## Then do the pre-processing on the data, like muting and Marine Gain.
			cmd5 = "<t2.H %s/wei_transf.x f1=4 f2=6 f3=16 f4=20 | Transp plane=12 reshape=1,3,5 >%s"%(bin_tang,fname_out2) 
			print cmd1,"\n",cmd2,"\n",cmd3,"\n",cmd4,"\n",cmd5
			status = -1
			if (os.system(cmd1) != 0):	err( "! Status is %d !"%(status))
			if (os.system(cmd2) != 0):	err( "! Status is %d !"%(status))
			if (os.system(cmd3) != 0):	err( "! Status is %d !"%(status))
			if (os.system(cmd4) != 0):	err( "! Status is %d !"%(status))
			if (os.system(cmd5) != 0):	err( "! Status is %d !"%(status))		
			#after that, clean the fname_out file
			cmd6 = "Rm3d %s"%(fname_out)
			if (os.system(cmd6) != 0):	print "! Status is %d !"%(status)
		
		elif oper=="verify": #Verify the binaries generated does not contain nan values.	
			#fname_out2="a.H"
			cmd1 = "Attr<%s | grep -E 'nan|inf' "%(fname_out2)
			stat1,out1=commands.getstatusoutput(cmd1)
			print cmd1,"\n",stat1,"\n",out1,
			#if (stat1 != 0 or out1!=""):
			if (stat1 == -1 or out1!=""):
				print "sth is wrong, stat1=%d,out1=%s"%(stat1,out1)
				exit(-1)
			else:
				print "%s is good"%fname_out2
		elif oper=="remotecp": #remote cp these files to cees clusters
			data_folder_remote="/data/sep/zyang03/data/waz/3d"
			cmd1 = "cp %s junk.H; sed -i 's/\/scr1\/yang/\/net\/tesla3\/scr1\/yang/g' junk.H"%(fname_out2)
			cmd2 = "echo in=" + data_folder_remote+"/"+fname_out2_base+"@ >> junk.H"
			cmd3 = "scp junk.H zyang03@cees-cluster:%s/%s"%(data_folder_remote,fname_out2_base)
			cmd4 = "scp /net/tesla3/scr1/yang/%s@ zyang03@10.1.5.11:%s/%s@"%(fname_out2_base,data_folder_remote,fname_out2_base)
			print cmd1,"\n",cmd2,"\n",cmd3,"\n",cmd4,"\n"
			status = -1
			if (os.system(cmd1) != 0):	err( "! Status is %d !"%(status))
			if (os.system(cmd2) != 0):	err( "! Status is %d !"%(status))
			if (os.system(cmd3) != 0):	err( "! Status is %d !"%(status))
			if (os.system(cmd4) != 0):	err( "! Status is %d !"%(status))
		else:
			print "invalid oper options"

