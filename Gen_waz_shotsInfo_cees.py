#!/usr/bin/python
import sys,re,os,string
import commands
import array
import os

sepbin=os.environ["SEP"]+"/bin"
debug=0

def err(m=""):
  """Quit with an error first printing out the string m"""
	#self_doc();
  if  debug==0:
    msg( m)
    sys.exit(-1)
  else:
    raise error,m
	
def msg(strng):
  """Print out a message to the screen, do a flush to guarantee immediate action"""
  lines=strng.split('\n')
  for line in lines:
    print  "     %s"%line 
  sys.stdout.flush()
 
class error(Exception):
   """A class for handling errors"""
   def __init__(self, value):
     self.value = value
   def __str__(self):
     lines=self.value.split('\n')
     msg( "\n")
     for line in lines:
       msg("     %s"%line)
     return repr()
     
def parse_args(args):
  eqs={}
  aout=[]
  eqs["basic_sep_io"]="0"
  eq=re.compile("^(.+)=(.+)$")
  for arg in args:
    a=eq.search(arg)
    if a:
       eqs[a.group(1)]=a.group(2)
    else:
       aout.append(arg)
  return eqs,aout   


def get_sep_params(file,par,o):
 for i in range(6):
   stat1,out1=commands.getstatusoutput("%s/Get parform=no <%s n%d"%(sepbin,file,i+1))
   stat2,out2=commands.getstatusoutput("%s/Get parform=no <%s o%d"%(sepbin,file,i+1))
   stat3,out3=commands.getstatusoutput("%s/Get parform=no <%s d%d"%(sepbin,file,i+1))
   stat4,out4=commands.getstatusoutput("%s/Get parform=no <%s label%d"%(sepbin,file,i+1))
   if stat1:
     err("Trouble reading parameters from %s"%file)
   if len(out1)==0:out1="1"
   if len(out2)==0:out2="0"
   if len(out3)==0:out3="1"
   if len(out4)==0:out4=" "
   if not par.has_key("n%s_%d"%(o,i+1)): par["n%s_%d"%(o,i+1)]=out1
   if not par.has_key("o%s_%d"%(o,i+1)): par["o%s_%d"%(o,i+1)]=out2
   if not par.has_key("d%s_%d"%(o,i+1)): par["d%s_%d"%(o,i+1)]=out3
   if not par.has_key("label%s_%d"%(o,i+1)): par["label%s_%d"%(o,i+1)]=out4
 return par

def get_sep_grid_params(file,par,o):
 for i in range(6):
   stat1,out1=commands.getstatusoutput("%s/In %s | grep n%d >log"%(sepbin,file,i+1))
	
   stat1,out1=commands.getstatusoutput("<log %s/Get parform=no n%d "%(sepbin,i+1))
   stat1,out2=commands.getstatusoutput("<log %s/Get parform=no o%d "%(sepbin,i+1))
   stat1,out3=commands.getstatusoutput("<log %s/Get parform=no d%d "%(sepbin,i+1))
   stat1,out4=commands.getstatusoutput("<log %s/Get parform=no label%d "%(sepbin,i+1))
   if stat1:
     err("Trouble reading parameters from %s"%file)
   if len(out1)==0:out1="1"
   if len(out2)==0:out2="0"
   if len(out3)==0:out3="1"
   if len(out4)==0:out4=" "
   if not par.has_key("n%s_%d"%(o,i+1)): par["n%s_%d"%(o,i+1)]=out1
   if not par.has_key("o%s_%d"%(o,i+1)): par["o%s_%d"%(o,i+1)]=out2
   if not par.has_key("d%s_%d"%(o,i+1)): par["d%s_%d"%(o,i+1)]=out3
   if not par.has_key("label%s_%d"%(o,i+1)): par["label%s_%d"%(o,i+1)]=out4
 return par

def get_segy_params(file,par,o,off):
  f=open(file,"rb");
  f.seek(off,0)
  array_i=array.array("i");
  array_i.fromfile(f,60)
  f.seek(off,0)
  array_h=array.array("h");
  array_h.fromfile(f,120)
  f.seek(off,0)
  array_f=array.array("f");
  array_f.fromfile(f,60)
  if not par.has_key("n%s_1"%o):  par["n%s_1"%o]=int(array_h[57]);
  if not par.has_key("d%s_1"%o): par["d%s_1"%o]=float(array_h[58])/1000000.;
  if not par.has_key("n%s_2"%o): par["n%s_2"%o]=int(array_i[51]);
  if not par.has_key("o%s_2"%o):  par["o%s_2"%o]=array_f[48];
  if not par.has_key("d%s_2"%o): par["d%s_2"%o]=array_f[47];
  return par


    
def pars_exist(ex,pars):
  if not pars.has_key("n%s_1"%ex) or not pars.has_key("n%s_2"%ex):
    return None
  return 1

def parse_position(args):
  hist=[]
  if args.has_key("position"):
    order=args["position"].split(",")
    if len(order) < 2:
       err("position should be a comma seperated list")
    for i in range(8-len(order)):
      order.append("0")
    hist.append("0-navigate-move-%s"%string.join(order,":"))
    del args["position"]
  return hist,args
         
def self_doc():
  print 
  print 
  print 
  print 
  print 

## This program will try to generate a meta information files for a large dataset that contains 
# many small pieces file into small pieces, and do stuff to extract the migration aperture for each files
# Usage:    *.py datagrid.H path=path_to_file_pieces offset=y aper_x=500 aper_y=600 f_src=csou.H beg6= end6= beg5= end5=

eq_args,args=parse_args(sys.argv[1:])
fname = args[0] #assume the target file name is the first argument
his_grid = {}
his_eachshot={}
get_sep_grid_params(fname,his_grid,'g')

#set global limits based on the size of velocity model
vxmin=2250;vxmax=36450;vymin=-18180;vymax=15960
print eq_args,"\n"
print "\n", his_grid,"\n"

# axis 5 and 6 are the shot_x and#ogx,ogy,osx,osy
#dgx,dgy,dsx,dsy
#ngx,ngy,nsx,nsy
base = os.path.basename(fname); base_wo_ext = os.path.splitext(base)[0]

#figureout the output shotsInfo file name
if eq_args.has_key("output"):
	fn_shotsInfo=eq_args["output"]
else:
	err("specify output!!!")

#fn_shotsInfo="%s/%s.shotsInfo"%(".",base_wo_ext)
fp_o = open(fn_shotsInfo,"w")
#fp_o = sys.stdout

fname_out = ""; fname_out2=""; path_out = ""; fname_out2_base=""
if eq_args.has_key("path"):
	path_out = eq_args["path"]
else:
	path_out = os.getcwd() #use the default, the current directory
path_out = os.path.abspath(path_out) #get the absolut path

#check if it is marine or land acquistion
bMarine = True
if eq_args.has_key("offset"):
	if (eq_args["offset"]=="n"):
		bMarine=False
else:
	err("specify offset=y/n, to indicate if it is marine or land acquisition")

aper_x_extra = 0
aper_y_extra = 0
if eq_args.has_key("aper_x"):
	aper_x_extra = float(eq_args["aper_x"])
if eq_args.has_key("aper_y"):
	aper_y_extra = float(eq_args["aper_y"])

fn_src = ""
if eq_args.has_key("f_src"):
	fn_src = eq_args["f_src"]
else:
	err("")
fn_src=os.path.abspath(fn_src)

#suffix for individual shot filenames
fn_suf=""
if eq_args.has_key("suf"):
	fn_suf = eq_args["suf"]

lines_output = []
bin_Y = "/net/server/yang/bin"

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

#determine how the file names are organized
#o5 = 8; n5=176
#o6=1; n6=21; j6=1
j5=1; j6=1

res5 = (n5-o5)%j5; res6 = (n6-o6)%j6
#extract the input's name, append the iy_ix info to the filename, and then append .H to it
icnt = 0

for iy in range(o6,n6,j6):
	#if (iy == n6-res6): #if it is the last block
	for ix in range(o5,n5,j5):
		#if (ix == n5-res5): #if it is the last block
		#fname_out = "%s/%s_%02d_%03d.H"%(path_out,base_wo_ext,iy,ix)
		fname_out2_base = "%s_%02d_%03d_c%s.H"%(base_wo_ext,iy,ix,fn_suf)
		fname_out2 = "%s/%s"%(path_out,fname_out2_base)
		print ix,iy,fname_out2
		#Now we have the files in fname_out2. First check its existance
		if not os.path.exists(fname_out2):
			err("%s does not exist!!! Check file fname_out2!"%fname_out2)
		#read in that files dimension
		his_eachshot={}
		get_sep_params(fname_out2,his_eachshot,"g")
		#need to extract the dimension information from each shot
		
		print fname_out2,his_eachshot
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
		
		icnt = icnt + 1
		print "icnt=%d, %f %f %f %f"%(icnt,ogx,ogy,osx,osy)
		#Calculate the migration aperture based on the src/recv locations
		if (bMarine):
			xmin = min(osx+ogx,osx)
			xmax = max(sx_max,sx_max+gx_max)
			ymin = min(osy+ogy,osy);
			ymax = max(sy_max,sy_max+gy_max)
		else:
			xmin = min(osx,ogx)
			xmax = max(sx_max,gx_max)
			ymin = min(osy,ogy);
			ymax = max(sy_max,gy_max)
		#If there is extra aperture added
		xmin = xmin-aper_x_extra; xmax = xmax + aper_x_extra
		ymin = ymin-aper_y_extra; ymax = ymax + aper_y_extra
		if (xmin<vxmin or xmax>vxmax or ymin<vymin or ymax>vymax):
			msg = "xmin=%f,vxmin=%f,xmax=%f,vxmax=%f,ymin=%f,vymin=%f,ymax=%f,vymax=%f"%(xmin,vxmin,xmax,vxmax,ymin,vymin,ymax,vymax) 
			print(msg); err(msg)
		lines_output.append("%s %5.3f %5.3f %5.3f %5.3f"%(fname_out2,xmin,xmax,ymin,ymax))
		print icnt,":%s"%(lines_output[icnt-1])
#Now create the first two lines of file
char = "y"
if (not bMarine):
	char = "n"
cmd1 = "%d bMarineGeom=%s singleSrcFileForAllShots=y %s \n"%(icnt,char,fn_src)
cmd2 = "fname_data xmin xmax ymin ymax \n"
fp_o.write(cmd1); fp_o.write(cmd2)
fp_o.writelines("\n".join(lines_output))
fp_o.write("\n")
fp_o.close()

