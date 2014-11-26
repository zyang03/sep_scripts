#!/usr/bin/python
import sys,re,os,string
import commands
import array
import os

sep_path=os.environ.get('SEP')
sepbin = sep_path+"/bin"
debug=0


def err(m=""):
  """Quit with an error first printing out the string m"""
  self_doc();
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
def parse_order(inum,arg):
  order=arg.split(",")
  iold=len(order)
  ohave=[]
  owant=[]
  for i in range(len(order)):
    owant.append(order[i])
    ohave.append(i+1)
  for i in range(8-len(order)): 
    owant.append(i+iold+1)
    ohave.append(i+iold+1)
  #this is a dumb approach but it should work
  lines=[]
  for i in range(7):
    if ohave[i] != int(owant[i]):
      found=None
     # print "looking for ",owant[i]
      for j in range(8):
        #print ohave[j]
        if int(ohave[j])==int(owant[i]):
           found=j
      if not found:
        err("Couldn't find all axes in order description %s, missing %d "%(arg,i+1))
      if i < found: lines.append("%d-orient-transpose-Swap(%d%d)"%(inum,
        i+1,found+1))
      else: lines.append("%d-orient-transpose-Swap(%d%d)"%(inum,
        found+1,i+1))
      k=ohave[i]; ohave[i]=ohave[found]; ohave[found]=k
  return lines 

def seminar_params():
  x=[]
  x.append("50-main-resize-2:623:1128:1000:750");
  x.append("0-view-font-arial-18-bold")
  return x
       
def self_doc():
  print 
  print 
  print 
  print 
  print 

def basic_run(eq_args,args):
  if len (sys.argv)==1:
    err("")
  ndat,args=find_files(args,eq_args)
  if args.has_key("nmo"):
   if args["nmo"]=="1":  ndat,args=velan_params(args,ndat)
  args,hist=set_initial_state(ndat,args)
  if args.has_key("valgrind"): command="valgrind --leak-check=full  %s"%binary
  else: command=binary
  for key,val in args.items():
    command+=" %s='%s'"%(key,val)
  print command
  os.system(command)
  if hist:
    commands.getstatusoutput("rm my_hist")

## This program will try to divide the per-4shots file pieces into single shot each
### Usage:	*.py gthnomigdem_grid3d_2.H path_in=tmp path_out=tmp2
eq_args,args=parse_args(sys.argv[1:])

## Need to have oper= option specified, otherwise don't know what operation to do

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
j5 = 4;j6 = 1; 
#if n5%j5 != 0 or n6%j6 !=0:
#	err("n5\%j5 or n6%j6 != 0")
o6=0; o5=0
if eq_args.has_key("o5"):
	o5 = int(eq_args["o5"])
if eq_args.has_key("o6"):
	o6 = int(eq_args["o6"])
if eq_args.has_key("n6"):
	n6 = int(eq_args["n6"])
res5 = n5%j5; res6 = n6%j6

#o5=180; n6=1; 
cmd1 = ""; cmd2=""; cmd3=""; cmd4=""; cmd5=""; cmd6=""
n6_wnd = j6

base = os.path.basename(fname); base_wo_ext = os.path.splitext(base)[0]
fname_in=""; fname_out=""; path_in=""; path_out = ""; fname_in_base=""; fname_out_base=""

if eq_args.has_key("path_in"):
	path_in = eq_args["path_in"]
else:
	path_in = "."
if eq_args.has_key("path_out"):
	path_out = eq_args["path_out"]

bin_tang = "/homes/sep/yang/from-other/yaxun_weo/bin"
bin_Y = "/net/server/yang/bin"
#extract the input's name, append the iy_ix info to the filename, and then append .H to it
path_out = os.path.abspath(path_out) #get the absolut path

for iy in range(o6,n6,j6):
	if (iy == n6-res6): #if it is the last block
		n6_wnd = res6
	n5_wnd = j5
	for ix in range(o5,n5,j5):
		if (ix == n5-res5): #if it is the last block
			n5_wnd = res5
		fname_in_base = "%s_%02d_%03d_c.H"%(base_wo_ext,iy,ix)
		fname_in = "%s/%s"%(path_in,fname_in_base)

		for iw in range(0,n5_wnd,1):
			fname_out_base = "%s_%02d_%03d_c.H"%(base_wo_ext,iy,ix+iw)
			fname_out = "%s/%s"%(path_out,fname_out_base)
	
			#window the data into small blocks.
			cmd1 = "Window3d <%s f4=%d n4=1 squeeze=n  >%s datapath=%s/ "%(fname_in,iw,fname_out,path_out)
			print cmd1,"\n"
			status = -1
			if (os.system(cmd1) != 0):	err( "! Status is %d !"%(status))
			
			## Do the testing
			cmd1 = "Attr<%s | grep -E 'nan|inf' "%(fname_out)
			stat1,out1=commands.getstatusoutput(cmd1)
			print cmd1,"\n",stat1,"\n",out1,
			#if (stat1 != 0 or out1!=""):
			if (stat1 == -1 or out1!=""):
				print "sth is wrong, stat1=%d,out1=%s"%(stat1,out1)
				exit(-1)
			else:
				print "%s is good"%fname_out
			
