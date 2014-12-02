import array
import commands
import inspect
import sys,re,os,string

sepbin=os.environ["SEP"]+"/bin"
debug=0

# Print the current line no.
def line_no():
  """ Return the current line number in our program."""
  return 'line %d:' % (inspect.currentframe().f_back.f_lineno)

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
 
def err(m=""):
  """Quit with an error first printing out the string m"""
	#self_doc();
  if  debug==0:
    msg( m)
    sys.exit(-1)
  else:
    raise error,m
	
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
  eq=re.compile("^(.+?)=(.+)$")
  for arg in args:
    a=eq.search(arg)
    if a:
       eqs[a.group(1)]=a.group(2)
    else:
       aout.append(arg)
  return eqs,aout   


def get_sep_axis_params(file, iaxis):
  """Note that iaxis is 1-based, returns a list of *strings* [n,o,d,label]."""
  stat1,out1=commands.getstatusoutput("%s/Get parform=no <%s n%d"%(sepbin,file,iaxis))
  stat2,out2=commands.getstatusoutput("%s/Get parform=no <%s o%d"%(sepbin,file,iaxis))
  stat3,out3=commands.getstatusoutput("%s/Get parform=no <%s d%d"%(sepbin,file,iaxis))
  stat4,out4=commands.getstatusoutput("%s/Get parform=no <%s label%d"%(sepbin,file,iaxis))
  if stat1:
    err("Trouble reading parameters about axis%d from %s" % (iaxis, file))
  if len(out1)==0:out1="1"
  if len(out2)==0:out2="0"
  if len(out3)==0:out3="1"
  if len(out4)==0:out4=" "
  return [out1, out2, out3, out4]

def get_sep_params(file,par,suffix):
  """par is a dictionary (both as input and as returned value) containing keys like 
  nsuffix_1, osuffix_1 etc."""
  for i in range(0,7):
    out1, out2, out3, out4 = get_sep_axis_params(file, i+1)
    if not par.has_key("n%s_%d"%(suffix,i+1)): par["n%s_%d"%(suffix,i+1)]=out1
    if not par.has_key("o%s_%d"%(suffix,i+1)): par["o%s_%d"%(suffix,i+1)]=out2
    if not par.has_key("d%s_%d"%(suffix,i+1)): par["d%s_%d"%(suffix,i+1)]=out3
    if not par.has_key("label%s_%d"%(suffix,i+1)): par["label%s_%d"%(suffix,i+1)]=out4
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


import ConfigParser

def RunShellCmd(cmd):
  stat1,out1=commands.getstatusoutput(cmd)
  if stat1 != 0:
    assert False, 'Shell cmd Failed: %s!' % out1
  return

def RetrieveAllEqArgs(eq_args_from_cmdline):
  '''Read other parameters from the .param file and combine it with the cmdline arguments. Notice that entries in eq_args will take priority if there are duplicate keys.'''
  eq_args = eq_args_from_cmdline
  if 'param' in eq_args:
    param_file = eq_args['param']
    dict_args = GetParamsFromIniFile(param_file, None)
    dict_args.update(eq_args)
  else:
    dict_args = eq_args
  # Find the current user name
  if 'user' not in dict_args:
    dict_args['user'] = os.environ['USER']
  return dict_args


def ConfigurationFromIniFile(param_file):
  '''Parse a Ini format parameter file, and return the config object.'''
  config = ConfigParser.ConfigParser()
  config.optionxform = str  # Set the configparser to preserve case, by default config Parser makes everything lowercase.
  config.read(param_file)
  return config


def GetParamsBySection(config, section):
  '''Return the parameters under a certain section as a dictionary.
  If section is None, then return all sections.
  '''
  sections_all = config.sections()
  secs = []
  if section in sections_all:
    secs.append(section)
  else:
    assert section is None, 'Un Recognized section name %s !' % section
    secs = sections_all
  dict = {}
  for sec in secs:
    for key in config.options(sec):
      val = config.get(sec, key)
      #print "[%s].%s = " % (sec, opt), val, type(val)
      assert key not in dict, 'Found duplicate entries for key=%s' % key
      dict[key] = val
  return dict

def GetParamsFromIniFile(param_filename, section=None):
  config = ConfigurationFromIniFile(param_filename)
  return GetParamsBySection(config, section)

