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

def find_files(args,eqs):
  """Find files and there type"""
  sufR=re.compile(".+\.(\S+)$")
  count=0;
  for arg in args:   
      if not os.path.exists(arg):
       err("%s is not a file. Expecting all arguments not of form a=b to be files to display"%arg)
      fnd=sufR.search(arg)
      if not fnd:
        if not eqs.has_key("type%d"%count):
          err("Couldn't find suffix for %s must specify type%d=X where X must be either:%s"%(
            arg,count,string.join(myt,",")))
        else:
          for suf,typ in sufixes.items():
            if typ==eqs["type%d"%count]:
              aa="aaa.%s"%typ
              fnd=sufR.search(aa);
      for suf,typ in sufixes.items():
        if fnd.group(1) == suf:
          eqs["type%d"%count]=typ
      if not eqs.has_key("type%d"%count):
          err("Don't recognize suffix for %s must specify type%d=X where X must be either:%s"%(
            arg,count,string.join(myt,",")))
      if not eqs.has_key("store%d"%count):
        eqs["store%d"%count]="IN_BYTE"
      if eqs["type%d"%count]=="SEP":
        if not pars_exist("g",eqs):
          get_sep_params(arg,eqs,"g")
      elif eqs["type%d"%count]=="SEISPAK":
        get_seispak_params(arg,eqs,count)
        if not pars_exist("g",eqs):
          eqs=copy_pars(eqs,"0","g");
      elif eqs["type%d"%count]=="SEGY":
        get_segy_params(arg,eqs,count,3600)
        if not pars_exist("g",eqs):
          eqs=copy_pars(eqs,"0","g");
      elif eqs["type%d"%count]=="SU":
        get_segy_params(arg,eqs,count,0)
        if not pars_exist("g",eqs):
          eqs=copy_pars(eqs,"0","g");
      elif eqs["type%d"%count]=="SEISPAK":
        get_seispak_params(arg,eqs,count)
        if not pars_exist("g",eqs):
          eqs=copy_pars(eqs,"0","g");
      else:
        if pars_exist("g",eqs): 
          eqs=copy_pars(eqs,"g",str(count))
        else:
          if count==0 and pars_exist("0",eqs):
            eqs=copy_pars(eqs,"0","g")
          else:
            err("Must specify data size")
        
      eqs["data%d"%count]=arg
      count+=1
  eqs["ndata"]=count
  return count,eqs

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
	 #if stat1:
	 #  err("Trouble reading parameters from %s"%file)
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


def copy_pars(pars,fr,to):
  for i in range(8):
    f="n%s_%d"%(fr,i+1); t="n%s_%d"%(to,i+1)
    if not pars.has_key(t) and  pars.has_key(f): pars[t]=pars[f]
    f="o%s_%d"%(fr,i+1); t="o%s_%d"%(to,i+1)
    if not pars.has_key(t) and  pars.has_key(f): pars[t]=pars[f]
    f="d%s_%d"%(fr,i+1); t="d%s_%d"%(to,i+1)
    if not pars.has_key(t) and  pars.has_key(f): pars[t]=pars[f]
    f="label%s_%d"%(fr,i+1); t="label%s_%d"%(to,i+1)
    if not pars.has_key(t) and  pars.has_key(f): pars[t]=pars[f]
  return pars
    
    
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

## This program will try to Window3d a big sep-3d data file into small pieces, do someprocessing and finally convert each piece to an individual sep77 files
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
#get_sep_params(fname,his_3d,'g')
get_sep_grid_params(fname,his_grid,'g')

print eq_args,"\n"
print "\n", his_3d,"\n"
print "\n", his_grid,"\n"

# axis 5 and 6 are the shot_x and shot_y axis, we should divide the data domain into small, for now, just do 2 by 2 blocks.
n5 = int(his_grid["ng_5"]); n6 = int(his_grid["ng_6"])

#test
#n5=2; n6=1

j5 = 4;j6 = 1
#if n5%j5 != 0 or n6%j6 !=0:
#	err("n5\%j5 or n6%j6 != 0")
res5 = n5%j5; res6 = n6%j6
o6 = 0

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
	for ix in range(0,n5,j5):
		if (ix == n5-res5): #if it is the last block
			n5_wnd = res5
		fname_out = "%s/%s_%02d_%03d.H"%(path_out,base_wo_ext,iy,ix)
		fname_out2_base = "%s_%02d_%03d_c.H"%(base_wo_ext,iy,ix)
		fname_out2 = "%s/%s"%(path_out,fname_out2_base)
		if (oper=="gen_c"):
			print "should not use oper==gen_c option in this script!!"
			exit(-1)
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

