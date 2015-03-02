#!/usr/bin/python
import sys,re,os,string
import commands
import array
import os

import math
from sepbase import *

def self_doc():
  print 
  print 
  print 
  print 
  print 

#see if two rectangles overlap or not
def is_rect_overlap(xmin1,xmax1,ymin1,ymax1,xmin2,xmax2,ymin2,ymax2):
	bOverLapX = (xmin1 >= xmin2 and xmin1 < xmax2) or (xmin2 >= xmin1 and xmin2 < xmax1)	
	bOverLapY = (ymin1 >= ymin2 and ymin1 < ymax2) or (ymin2 >= ymin1 and ymin2 < ymax1)	
	return bOverLapX,bOverLapY

#grow a xy-rectangle region for begx,endx,begy,endy
def pad_xy_region(xmin,xmax,ymin,ymax,begx,endx,begy,endy):
	return xmin-begx,xmax+endx,ymin-begy,ymax+endy

## This program will try to select shotsInfo from a full-list of shotsInfo based on the region of interest
## The output is also a shotsInfo type file
# Usage:    *.py fname.shotsInfo output=fout.shotsInfo roi_x=xmin,xmax roi_y=ymin,ymax [roi_z=zmin,zmax] I_depth=imaging_depth I_angle=imaging_angle
# "I_depth and I_angle" controls how much the ROI would expand on surface, typical value of I_angle = 30

# Currently the program does not consider roi_z
eq_args,args=parse_args(sys.argv[1:])
his_eachshot={}
#get_sep_grid_params(fname,his_grid,'g')
#set global limits based on the size of velocity model
vxmin=2250;vxmax=36450;vymin=-18180;vymax=15960
print eq_args,"\n"

fno_shotsInfo = ""; fni_shotsInfo = ""
fni_shotsInfo = args[0]
if eq_args.has_key("output"):
	fno_shotsInfo=eq_args["output"]
else:
	err("specify output!!!")

I_depth = 10000 #10km
if eq_args.has_key("I_depth"):
	I_depth=float(eq_args["I_depth"])
I_angle = 30
if eq_args.has_key("I_angle"):
	I_angle=math.radians(float(eq_args["I_angle"]))
xpad = math.tan(I_angle)*I_depth; ypad = math.tan(I_angle)*I_depth
print "xpad=%f,ypad=%f" % (xpad,ypad)

fp_i = open(fni_shotsInfo,"r"); fp_o = open(fno_shotsInfo,"w")
#Read in the region of interest
roi_xmin=roi_xmax=0;roi_ymin=0;roi_ymax=0;roi_zmin=0;roi_zmax=0
if eq_args.has_key("roi_x"):
	str_xs = eq_args["roi_x"].split(",")
	roi_xmin = float(str_xs[0]); roi_xmax = float(str_xs[1])
else:
	err("no roi_x= !!")
if eq_args.has_key("roi_y"):
	str_ys = eq_args["roi_y"].split(",")
	roi_ymin = float(str_ys[0]); roi_ymax = float(str_ys[1])
else:
	err("no roi_y= !!")
if eq_args.has_key("roi_z"):
	str_zs = (eq_args["roi_z"]).split(",")
	roi_zmin = float(str_zs[0]); roi_zmax = float(str_zs[1])
else:
	print "no roi_z"
print "roi dimensions", roi_xmin,roi_xmax,roi_ymin,roi_ymax
roi_xmin,roi_xmax,roi_ymin,roi_ymax = pad_xy_region(roi_xmin,roi_xmax,roi_ymin,roi_ymax,xpad,xpad,ypad,ypad)
print "roi dimensions after pad", roi_xmin,roi_xmax,roi_ymin,roi_ymax

## Parse the input shotsInfo file, and select useful shots based on the region of interest information, also output total migration domain required to accommodate the final dataset
lines_output = []
bin_Y = "/net/server/yang/bin"
iline=0; bMarine = True; nfiles = 0; ifcnt = 0
line = ""; line2=""; strlist_line1 = [];
b_enterY = False
while 1:
	line = fp_i.readline();
	if not line: #ifeof
		break
	else:
		line = line.rstrip('\n')
		if line!="": ## parse each line
			iline = iline+1
			if iline==1: ## first line, important info needs to be extracted, first line exp: 420 bMarineGeom=y singleSrcFileForAllShots=y /data/sep/zyang03/data/waz/csou-waz3d.H 
				strlist_line1 = line.split(" ")
				nfiles = int(strlist_line1[0])
				char_offset = strlist_line1[1].split("=")[1]
				if char_offset == "n" or char_offset == "0":
					bMarine = False
			if iline==2: ## second line, exp: fname_data xmin xmax ymin ymax 
				line2 = line
				str_lists = (line).split(" ")
				if (str_lists[0] != "fname_data"):
					err("2nd line begining is 'fname_data'")
			if iline>2: # the rest, start with the shots filename
				str_lists = (line).split(" ")
				fn_shot = str_lists[0] #read the geom information of the shot file
				his_eachshot={}; get_sep_axes_params(fn_shot,his_eachshot,"g")
				#print fn_shot,his_eachshot
				ogx = float(his_eachshot["og_1"]); ngx=int(his_eachshot["ng_1"]); dgx=float(his_eachshot["dg_1"])
				ogy = float(his_eachshot["og_2"]); ngy=int(his_eachshot["ng_2"]); dgy=float(his_eachshot["dg_2"])
				osx = float(his_eachshot["og_4"]); nsx=int(his_eachshot["ng_4"]); dsx=float(his_eachshot["dg_4"])
				osy = float(his_eachshot["og_5"]); nsy=int(his_eachshot["ng_5"]); dsy=float(his_eachshot["dg_5"])
				sx_max = osx+(nsx-1)*dsx; sy_max = osy+(nsy-1)*dsy
				gx_max = ogx+(ngx-1)*dgx; gy_max = ogy+(ngy-1)*dgy
				if (sx_max < osx): err("F1")
				if (sy_max < osy): err("F2")
				if (gx_max < ogx): err("F3") 
				if (gy_max < ogy): err("F4")
				print "icnt=%d, %f %f %f %f"%(ifcnt,ogx,ogy,osx,osy)
				#Calculate the midpoint aperture based on the src/recv locations
				if (bMarine):
					xmmin = ((osx+ogx)+osx)*0.5;	xmmax = (sx_max+(sx_max+gx_max))*0.5
					ymmin = ((osy+ogy)+osy)*0.5;	ymmax = (sy_max+(sy_max+gy_max))*0.5
				else:
					xmmin = (osx+ogx)*0.5;	xmmax = (sx_max+gx_max)*0.5
					ymmin = (osy+ogy)*0.5;	ymmax = (sy_max+gy_max)*0.5
				wid_x = xmmax-xmmin; wid_y = ymmax-ymmin
				#if this shot is relavant
				x_overlap,y_overlap = is_rect_overlap(xmmin,xmmax,ymmin,ymmax,roi_xmin,roi_xmax,roi_ymin,roi_ymax)
				if (x_overlap and y_overlap):
					b_enterY = True
					print "midpt dimensions", xmmin,xmmax,ymmin,ymmax
					ifcnt = ifcnt+1; lines_output.append(line)
				#if (not y_overlap and b_enterY):
				#	break
#Put the first two lines of the output file in place
cmd1 = "%d %s\n"%(ifcnt," ".join(strlist_line1[1:])); cmd2 = line2
fp_o.write(cmd1); fp_o.write(line2+"\n")
fp_o.write("\n".join(lines_output))
fp_o.write("\n")
fp_o.close(); fp_i.close()

