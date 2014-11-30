import ConfigParser

if __name__ == "__main__":
  config = ConfigParser.ConfigParser()
  config.read('test.param')
  secs = config.sections()
  for sec in secs:
    for opt in config.options(sec):
      val = config.get(sec, opt)
      print "[%s].%s = " % (sec, opt), val, type(val)

