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

## This program will try to batch generate migration pbs scripts based on shotsInfo file 

# Usage1:    *.py pbs_script_tmpl.sh nfiles=1001 nfiles_perbatch=10 path=path_out prefix-img=img-waz3d queue=q35 nnodes=0 njobmax=5 ish_beg=0 nbatch=? add_cmdline_pars=
# Usage2:		 User can also supply a list of ish_begs to start with
#						 *.py pbs_script_tmpl.sh nfiles=1001 path=path_out prefix-img=img-waz3d queue=q35 nnodes=0 njobmax=5 ish_beglist=? nfiles_perbatch=10 add_cmdline_pars=

eq_args,args=parse_args(sys.argv[1:])
fname_tmpl_script = args[0] #assume the target file name is the first argument
#separate the files and path
base = os.path.basename(fname_tmpl_script); base_wo_ext = os.path.splitext(base)[0]

path_out = "."; prefix_img = "imgh-waz3d"

n=0;N=0

if eq_args.has_key("nfiles"):
	N=int(eq_args["nfiles"])
else:
	err("specify nfiles!!!")
if eq_args.has_key("nfiles_perbatch"):
	n=int(eq_args["nfiles_perbatch"])
else:
	err("specify nfiles_perbatch!!!")

#cmds line that directly pass to MPI program (Migration.mx)
add_cmdl_pars = ""
if eq_args.has_key("add_cmdline_pars"):
	add_cmdl_pars = eq_args["add_cmdline_pars"]
print "add_cmdl_pars:" , add_cmdl_pars

if eq_args.has_key("path"):
	path_out = eq_args["path"]
else:
	path_out = os.getcwd() #use the default, the current directory
if eq_args.has_key("prefix-img"):
	prefix_img = eq_args["prefix-img"]

queue = "default"
if eq_args.has_key("queue"):
	queue = eq_args["queue"]

nnodes = 0
if eq_args.has_key("nnodes"):
	nnodes = int(eq_args["nnodes"])
if eq_args.has_key("prefix-img"):
	prefix_img = eq_args["prefix-img"]

njob_max = 1
if eq_args.has_key("njobmax"):
	njob_max = int(eq_args["njobmax"])
print njob_max

##Learn the velocity file and the shotsInfo file
fn_v3d = ""; fn_shotsInfo = ""
if eq_args.has_key("vel"):
	fn_v3d				= (eq_args["vel"])
if eq_args.has_key("shotsInfo"):
	fn_shotsInfo	= (eq_args["shotsInfo"])

bInputFileList = False
ish_start = 0; ish_flist = ""
ishotLists = []
b_ish_beg			= eq_args.has_key("ish_beg")
b_ish_beglist = eq_args.has_key("ish_beglist")

if b_ish_beg and b_ish_beglist:
	err("!!! cannot have both: ish_beg & ish_beglist")
if (not b_ish_beg) and (not b_ish_beglist):
	err("! Need to supply one of the two: ish_beg or ish_beglist!!")

if b_ish_beg:
	ish_start = int(eq_args["ish_beg"])
	bInputFileList = False
	ishotLists = range(ish_start,N,n)
if b_ish_beglist:
	ish_flist = eq_args["ish_beglist"]
	bInputFileList = True
	# read the list files to generate a list of shots
	fp_list = open(ish_flist,'r')
	line = ""
	while 1:
		line = fp_list.readline();
		if not line:
			break
		else: ## turn this line into a number, ascii 10 is linefeed
			if line != "" and line != chr(10):
				#print "line=",line; print ord(line[-1]), len(line)
				ishotLists.append(int(line))

print 

nbatch = N #set nbatch to be big enough
if eq_args.has_key("nbatch"):
	if (eq_args["nbatch"] != ""):
		nbatch = int(eq_args["nbatch"])
print "ish_start=%d : ish_flist=%s : nbatch=%d"%(ish_start,ish_flist,nbatch)

path_out = os.path.abspath(path_out) #get the absolut path
status = -1
cmd1 = ""; cmd2 = ""
fp_o = []
sz_shotrange = ""

print len(ishotLists),"ishotLists=", ishotLists

njob = 0; ibatch=0
for ish in ishotLists:
	ibatch = ibatch + 1
	if (ibatch > nbatch):
		break
	nsh = min(N-ish,n)
	sz_shotrange = "%04d_%04d" % (ish,ish+nsh)
	fn_script = '%s/%s.%s'	%(path_out,base,sz_shotrange)
	fn_log = '%s/%s-%s.log'	%(path_out,prefix_img,sz_shotrange)
	fn_imgh = "%s/%s-%s.H"	%(path_out,prefix_img,sz_shotrange)

	cmd1 = "cp %s %s \n"%(fname_tmpl_script,fn_script)
	print cmd1,"\n"
	if (os.system(cmd1) != 0):	err( "! Status is %d !"%(status))
	if (queue!=""): #need to change the queue name
		cmd1 = "sed -i 's/#PBS\ -q\ default/#PBS\ -q\ %s/g'   %s"%(queue,fn_script)
		if (os.system(cmd1) != 0):	
			print line_no();
			err( "! Status is %d !"%(status))
	if (nnodes!=0): #need to change the number of nodes 
		cmd1 = "sed -i 's/#PBS\ -l\ nodes=1/#PBS\ -l\ nodes=%d/g'   %s"%(nnodes,fn_script)
		if (os.system(cmd1) != 0):	
			print line_no();
			err( "! Status is %d !"%(status))
	#replace vmod or shots data info if needed
	if (fn_v3d!=""):
		cmd1 = "sed -i 's/#V3D_Z20_VTANG#/%s/g' %s"%(fn_v3d,fn_script)
		if (os.system(cmd1) != 0):	
			print line_no();
			err( "! Status is %d !"%(status))
	if (fn_shotsInfo!=""):
		cmd1 = "sed -i 's/#D3D_NOMIGDEM_SHOTSINFO#/%s/g' %s"%(fn_shotsInfo,fn_script)
		if (os.system(cmd1) != 0):	
			print line_no();
			err( "! Status is %d !"%(status))
		
	#Append a cmd to the bottom of the copied script file
	fp_o = open(fn_script,'a')
	cmd2 = "${cmd} ishot_beg=%d ishot_end=%d \'>& %s\' imgh=%s add_migpar_1w=\" ${MIG_PAR_WAZ3D} \" %s \n" % (ish,ish+nsh,fn_log,fn_imgh, add_cmdl_pars)
	#first echo the cmd to stdoutput for debug purpose, then execute that
	fp_o.write("echo " + cmd2 + " \n");
	cmd1 = "${cmd} ishot_beg=%d ishot_end=%d >& %s imgh=%s add_migpar_1w=\" ${MIG_PAR_WAZ3D} \" %s \n" % (ish,ish+nsh,fn_log,fn_imgh, add_cmdl_pars)
	fp_o.write(cmd1+"\n")
	fp_o.close()
	
	#submit the job script to pbs system by looking at if there are enough running jobs
	jobC = 0; jobR = 0; jobQ = 0
	while 1:
		print "starting on ishot: ", ish
		stat1,out1=commands.getstatusoutput('qstat | grep zyang03 | grep \' C \' | wc -l ')
		
		cmd1 = "qstat | grep zyang03 | grep \' R \' | grep %s| wc -l "%(queue)
		stat2,out2=commands.getstatusoutput(cmd1)
		cmd1 = "qstat | grep zyang03 | grep \' Q \' | grep %s| wc -l "%(queue)
		stat3,out3=commands.getstatusoutput(cmd1)
		jobC = int(out1); jobR = int(out2); jobQ = int (out3)
		print jobC," ",jobR,' ',jobQ
		njob = jobR + jobQ
		if (njob < njob_max): #submit a new job
			cmd1 = "qsub %s" % (fn_script)
			print line_no(),": submitting a new job",cmd1
			os.system(cmd1)
			os.system("sleep 1")
			break
		else:
			print "waiting on the pbs queue"
		os.system("sleep 180") #sleep 3mins before do the query again

	print "ish=",ish, n, N

