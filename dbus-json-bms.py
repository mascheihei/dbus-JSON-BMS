#!/usr/bin/env python
 
# import normal packages
import platform 
import logging
from logging.handlers import TimedRotatingFileHandler
import sys
import os
import sys
if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject
import sys
import time
import requests # for http GET
import configparser # for config/ini file
 
# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService


class DbusJSONBMSService:
  def __init__(self, servicename, deviceinstance, productname='JSON BMS', connection='JK BMS HTTP JSON service'):
    self._dbusservice = VeDbusService("{}.http_{:02d}".format(servicename, deviceinstance))
    config = self._getConfig()
    #get Params used internally
    self.allow_max_voltage = True
    self.max_voltage_start_time = None
    self.cccm_enable = config['Battery']['CCCMEnable']
    self.cvcm_enable = config['Battery']['CVCMEnable']
    self.cell_volt = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    self.url = self._getJSONBMSStatusUrl()
    self.float_cell_voltage = float(config['Battery']['FloatCellVoltage'])
    self.soc_level_reset_voltage = float(config['Battery']['SOCLevelToResetVoltageLimit'])
    self.max_voltage_time = float(config['Battery']['MaxVoltageTimeSec']) 
    self.control_allow_discharge = 1
    self.control_discharge_hys = True
    logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))
    # Create the management objects, as specified in the ccgx dbus-api document
    self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
    self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self._dbusservice.add_path('/Mgmt/Connection', connection)
    # Create the mandatory objects
    self._dbusservice.add_path('/DeviceInstance', deviceinstance)
    self._dbusservice.add_path('/ProductId', 0x0) 
    self._dbusservice.add_path('/ProductName', productname)
    self._dbusservice.add_path('/FirmwareVersion', 0.1)
    self._dbusservice.add_path('/HardwareVersion', 0)
    self._dbusservice.add_path('/Connected', 1)
    # Create static battery info
    self.number_of_cells = int(config['Battery']['NumberOfCells'])
    self._dbusservice.add_path('/System/NrOfCellsPerBattery', self.number_of_cells, writeable=True)
    self.min_cell_voltage = float(config['Battery']['MinCellVoltage'])
    self.min_battery_voltage = self.number_of_cells * self.min_cell_voltage
    self._dbusservice.add_path('/Info/BatteryLowVoltage', self.min_battery_voltage, writeable=True)
    self.max_cell_voltage = float(config['Battery']['MaxCellVoltage'])
    self.max_battery_voltage = self.number_of_cells * self.max_cell_voltage
    self._dbusservice.add_path('/Info/MaxChargeVoltage', self.max_battery_voltage, writeable=True,
                               gettextcallback=lambda p, v: "{:0.2f}V".format(v))
    self.max_charge_current = float(config['Battery']['MaxBatteryChargeCurrent'])
    self.control_charge_current = self.max_charge_current
    self._dbusservice.add_path('/Info/MaxChargeCurrent', self.max_charge_current, writeable=True,
                               gettextcallback=lambda p, v: "{:0.2f}A".format(v))
    self.max_discharge_current = float(config['Battery']['MaxBatteryDischargeCurrent'])
    self.control_discharge_current = self.max_discharge_current
    self._dbusservice.add_path('/Info/MaxDischargeCurrent', self.max_discharge_current,
                               writeable=True, gettextcallback=lambda p, v: "{:0.2f}A".format(v))
    self._dbusservice.add_path('/System/NrOfModulesOnline', 1, writeable=True)
    self._dbusservice.add_path('/System/NrOfModulesOffline', 0, writeable=True)
    self._dbusservice.add_path('/System/NrOfModulesBlockingCharge', None, writeable=True)
    self._dbusservice.add_path('/System/NrOfModulesBlockingDischarge', None, writeable=True)
    self.installed_capacity = int(config['Battery']['BatteryCapacity'])
    self._dbusservice.add_path('/InstalledCapacity', self.installed_capacity, writeable=True,
                               gettextcallback=lambda p, v: "{:0.0f}Ah".format(v))

    self._dbusservice.add_path('/Capacity', None, writeable=True,
                               gettextcallback=lambda p, v: "{:0.0f}Ah".format(v))
                               
    self._dbusservice.add_path('/ConsumedAmphours', None, writeable=True,
                               gettextcallback=lambda p, v: "{:0.0f}Ah".format(v))
    # Create SOC, DC and System items
    self._dbusservice.add_path('/Soc', None, writeable=True)
    self._dbusservice.add_path('/Dc/0/Voltage', None, writeable=True, gettextcallback=lambda p, v: "{:2.2f}V".format(v))
    self._dbusservice.add_path('/Dc/0/Current', None, writeable=True, gettextcallback=lambda p, v: "{:2.2f}A".format(v))
    self._dbusservice.add_path('/Dc/0/Power', None, writeable=True, gettextcallback=lambda p, v: "{:0.0f}W".format(v))
    self._dbusservice.add_path('/Dc/0/Temperature', None, writeable=True)
    self._dbusservice.add_path('/Dc/0/MidVoltage', None, writeable=True,
                                gettextcallback=lambda p, v: "{:0.2f}V".format(v))
    self._dbusservice.add_path('/Dc/0/MidVoltageDeviation', None, writeable=True,
                                gettextcallback=lambda p, v: "{:0.1f}%".format(v))
    # Create battery extras
    self._dbusservice.add_path('/System/MinCellTemperature', None, writeable=True)
    self._dbusservice.add_path('/System/MaxCellTemperature', None, writeable=True)
    self.cell_now_max_voltage = 0.0
    self._dbusservice.add_path('/System/MaxCellVoltage', self.cell_now_max_voltage, writeable=True,
                               gettextcallback=lambda p, v: "{:0.3f}V".format(v))
    self.cell_max_id = 0
    self._dbusservice.add_path('/System/MaxVoltageCellId', self.cell_max_id, writeable=True)
    self.cell_now_min_voltage = 0.0
    self._dbusservice.add_path('/System/MinCellVoltage', self.cell_now_min_voltage, writeable=True,
                               gettextcallback=lambda p, v: "{:0.3f}V".format(v))
    self.cell_min_id = 0                           
    self._dbusservice.add_path('/System/MinVoltageCellId', self.cell_min_id, writeable=True)
    self._dbusservice.add_path('/History/ChargeCycles', None, writeable=True)
    self._dbusservice.add_path('/History/TotalAhDrawn', None, writeable=True)
    self._dbusservice.add_path('/Balancing', None, writeable=True)
    self._dbusservice.add_path('/Io/AllowToCharge', 0, writeable=True)
    self._dbusservice.add_path('/Io/AllowToDischarge', 0, writeable=True)
    # self._dbusservice.add_path('/SystemSwitch',1,writeable=True)
    self._dbusservice.add_path('/Voltages/Cell1', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    self._dbusservice.add_path('/Voltages/Cell2', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    self._dbusservice.add_path('/Voltages/Cell3', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    self._dbusservice.add_path('/Voltages/Cell4', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    self._dbusservice.add_path('/Voltages/Cell5', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    self._dbusservice.add_path('/Voltages/Cell6', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    self._dbusservice.add_path('/Voltages/Cell7', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    self._dbusservice.add_path('/Voltages/Cell8', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    self._dbusservice.add_path('/Voltages/Cell9', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    self._dbusservice.add_path('/Voltages/Cell10', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    self._dbusservice.add_path('/Voltages/Cell11', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    self._dbusservice.add_path('/Voltages/Cell12', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    self._dbusservice.add_path('/Voltages/Cell13', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    self._dbusservice.add_path('/Voltages/Cell14', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    self._dbusservice.add_path('/Voltages/Cell15', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    self._dbusservice.add_path('/Voltages/Cell16', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))

    self._dbusservice.add_path('/Voltages/Sum', None, writeable=True, gettextcallback=lambda p, v: "{:2.2f}V".format(v))
    self._dbusservice.add_path('/Voltages/Diff', None, writeable=True, gettextcallback=lambda p, v: "{:1.3f}V".format(v))
    # Create the alarms
    self._dbusservice.add_path('/Alarms/LowVoltage', None, writeable=True)
    self._dbusservice.add_path('/Alarms/HighVoltage', None, writeable=True)
    self._dbusservice.add_path('/Alarms/LowCellVoltage', None, writeable=True)
    self._dbusservice.add_path('/Alarms/HighCellVoltage', None, writeable=True)
    self._dbusservice.add_path('/Alarms/LowSoc', None, writeable=True)
    self._dbusservice.add_path('/Alarms/HighChargeCurrent', None, writeable=True)
    self._dbusservice.add_path('/Alarms/HighDischargeCurrent', None, writeable=True)
    self._dbusservice.add_path('/Alarms/CellImbalance', None, writeable=True)
    self._dbusservice.add_path('/Alarms/InternalFailure', None, writeable=True)
    self._dbusservice.add_path('/Alarms/HighChargeTemperature', None, writeable=True)
    self._dbusservice.add_path('/Alarms/LowChargeTemperature', None, writeable=True)
    self._dbusservice.add_path('/Alarms/HighTemperature', None, writeable=True)
    self._dbusservice.add_path('/Alarms/LowTemperature', None, writeable=True)
    self._dbusservice.add_path('/Serial', '1234')
    self._dbusservice.add_path('/UpdateIndex', 0)
    # last update
    self._lastUpdate = 0
    # add _update function 'timer'
    gobject.timeout_add(3766, self._update) # pause 250ms before the next request   
    # add _signOfLife 'timer' to get feedback in log in minutes
    value = self._getSignOfLifeInterval()*60*1000
    gobject.timeout_add(value, self._signOfLife)
 

  def _getConfig(self):
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
    return config;
 
 
  def _getSignOfLifeInterval(self):
    config = self._getConfig()
    value = config['DEFAULT']['SignOfLifeLog']
    if not value: 
        value = 0
    return int(value)
  
  
  def _getJSONBMSStatusUrl(self):
    config = self._getConfig()
    accessType = config['DEFAULT']['AccessType']    
    if accessType == 'OnPremise': 
        URL = "http://%s:%s@%s" % (config['ONPREMISE']['Username'], config['ONPREMISE']['Password'], config['ONPREMISE']['Host'])
        URL = URL.replace(":@", "")
    else:
        raise ValueError("AccessType %s is not supported" % (config['DEFAULT']['AccessType']))
    return URL
    
 
  def _getJSONBMSData(self):
    try:
      bms_r = requests.get(self.url, timeout=5)
    except Exception as e:
      logging.info("No response from JK BMS")
      return False
    try:
      bms_data = bms_r.json()         
    # check for Json
    except Exception as e:
      logging.info("Converting response to JSON failed")
      return False
    return bms_data
    

  def _get_min_max_cell(self):
    min_voltage = 9999
    max_voltage = 0
    min_cell = None
    max_cell = None
    for i in range(self.number_of_cells):
      if self.cell_volt[i] < min_voltage:
        min_voltage = self.cell_volt[i]
        min_cell = i
      if self.cell_volt[i] > max_voltage:
        max_voltage = self.cell_volt[i]
        max_cell = i    
    self.cell_now_max_voltage = max_voltage
    self.cell_max_id = max_cell
    self.cell_now_min_voltage = min_voltage
    self.cell_min_id = min_cell
 
 
 
  def _signOfLife(self):
    logging.info("--- Start: sign of life ---")
    logging.info("Last _update() call: %s" % (self._lastUpdate))
    logging.info("Last '/DC/Power': %s" % (self._dbusservice['/Dc/0/Power']))
    logging.info("--- End: sign of life ---")
    return True
 
# next two functions are the core of BMS controlling and managing Voltage and Current depending on SoC and Voltage
  
  def _manage_charge_current(self):
        # If disabled make sure the default values are set and then exit 
    if (not self.cccm_enable):
        self.control_charge_current = self.max_charge_current
        self.control_discharge_current = self.max_discharge_current
        self.control_allow_charge = 1
        self.control_allow_discharge = 1
        return
    if self.soc is None:
            # Prevent JSON BMS from terminating on error
        return False
        # Charge depending on the SOC values       
    if self.soc > 99:
        self.control_allow_charge = 0
    else:
        self.control_allow_charge = 1
    if 98 < self.soc <= 100:
        self.control_charge_current = 5
    elif 95 < self.soc <= 98:
        self.control_charge_current = self.max_charge_current/4
    elif 91 < self.soc <= 95:
        self.control_charge_current = self.max_charge_current/2
    else:
        self.control_charge_current = self.max_charge_current 
        # Discharge depending on the SOC values
    if self.soc < 5:
        self.control_allow_discharge = 0
    elif self.control_discharge_hys == True:
        self.control_allow_discharge = 1        
    if self.soc <= 10 and self.control_discharge_hys == True:
        self.control_discharge_current = 5
    elif 10 < self.soc <= 20 and self.control_discharge_hys == True:
        self.control_discharge_current = self.max_discharge_current/2
    elif self.control_discharge_hys == True:
        self.control_discharge_current = self.max_discharge_current
    # Discharge depending on Low voltage has higher priority SoC could be a wrong estimation to avoid switching effects hysteresis is built in
    if self.cell_now_min_voltage < self.min_cell_voltage:
        self.control_allow_discharge = 0
        self.control_discharge_current = 0
        self.control_discharge_hys = False
    elif self.cell_now_min_voltage > (self.min_cell_voltage + 0.15):
        self.control_allow_discharge = 1
        self.control_discharge_hys = True

        
  def _manage_charge_voltage(self):
    voltageSum = 0
    if (self.cvcm_enable):
       for i in range(self.number_of_cells):
         voltage = self.cell_volt[i]
         if voltage:
            voltageSum+=voltage
       if None == self.max_voltage_start_time:
         if (self.max_cell_voltage * self.number_of_cells <= voltageSum) and (True == self.allow_max_voltage):
            self.max_voltage_start_time = time.time()
         else:
            if self.soc_level_reset_voltage > self.soc and not self.allow_max_voltage:
               self.allow_max_voltage = True
       else:
         tDiff = time.time() - self.max_voltage_start_time
         if self.max_voltage_time < tDiff:
            self.max_voltage_start_time = None
            self.allow_max_voltage = False
    if self.allow_max_voltage:
       self.control_voltage = self.max_cell_voltage * self.number_of_cells
    else:
       self.control_voltage = self.float_cell_voltage * self.number_of_cells    
 
 
  def _update(self):   
    try:
       #get data from JSON BMS
       bms_data = self._getJSONBMSData()
       if bms_data == False:
          logging.info("-- bms_data return is False in _update_")
          if ((time.time() - self._lastUpdate) > 60):    
            logging.info("-- shut down BMS")
            logging.info((time.time() - self._lastUpdate))
          return True
       for i in range(self.number_of_cells):   
          self.cell_volt[i] = float(bms_data['Cell'][str(i)])
       # Update SOC, DC and System items
       self.soc = int(bms_data['Battery']['Percent_Remain'])   
       self._dbusservice['/Soc'] = self.soc
       self._dbusservice['/Dc/0/Voltage'] = round(float(bms_data['Battery']['Battery_Voltage']), 2)
       self._dbusservice['/Dc/0/Current'] = round(float(bms_data['Battery']['Charge_Current']), 1)
       self._dbusservice['/Dc/0/Power'] = round(float(bms_data['Battery']['Battery_Power']), 1)
       self._dbusservice['/Dc/0/Temperature'] = round(float(bms_data['Battery']['Battery_T1']), 1)
       self._dbusservice['/Capacity'] = round(float(float(self.installed_capacity) * float(self.soc) / 100.0) , 1)
       self._dbusservice['/ConsumedAmphours'] = self.installed_capacity - self._dbusservice['/Capacity'] 
        # Update battery extras
       self._dbusservice['/History/ChargeCycles'] = int(bms_data['Battery']['Cycle_Count'])
       if float(bms_data['Battery']['Battery_T1']) < float(bms_data['Battery']['Battery_T2']):
         self.min_cell_temp = float(bms_data['Battery']['Battery_T1'])
         self.max_cell_temp = float(bms_data['Battery']['Battery_T2'])
       else: 
         self.min_cell_temp = float(bms_data['Battery']['Battery_T2'])
         self.max_cell_temp = float(bms_data['Battery']['Battery_T1'])
       self._dbusservice['/System/MinCellTemperature'] = self.min_cell_temp
       self._dbusservice['/System/MaxCellTemperature'] = self.max_cell_temp
       # Updates from cells
       self._get_min_max_cell()
       self._dbusservice['/System/MinVoltageCellId'] = self.cell_min_id
       self._dbusservice['/System/MaxVoltageCellId'] = self.cell_max_id
       self._dbusservice['/System/MinCellVoltage'] = self.cell_now_min_voltage
       self._dbusservice['/System/MaxCellVoltage'] = self.cell_now_max_voltage
       # Charge control
       self._manage_charge_current()   
       self._dbusservice['/Info/MaxChargeCurrent'] = self.control_charge_current
       self._dbusservice['/Info/MaxDischargeCurrent'] = self.control_discharge_current
#       self._dbusservice['/History/TotalAhDrawn'] = self.battery.total_ah_drawn
       # BMS "off" overrules "on/off" from this BMS control
       if bms_data['Battery']['Charge'] == "off":
         self._dbusservice['/Io/AllowToCharge'] = 0
       else:
         self._dbusservice['/Io/AllowToCharge'] = self.control_allow_charge
       # BMS "off" overrules "on/off" from this BMS control
       if bms_data['Battery']['Discharge'] == "off":
         self._dbusservice['/Io/AllowToDischarge'] = 0
       else:
         self._dbusservice['/Io/AllowToDischarge'] = self.control_allow_discharge
       # Voltage control
       self._manage_charge_voltage()
       self._dbusservice['/Info/MaxChargeVoltage'] = self.control_voltage

 # Alarm and Balancing still not part of JSON Files. Has to be updated
#       self._dbusservice['/Balancing'] = 
        # Update the alarms
#       self._dbusservice['/Alarms/LowVoltage'] = 
#        self._dbusservice['/Alarms/LowCellVoltage'] = 
#        self._dbusservice['/Alarms/HighVoltage'] = 
#        self._dbusservice['/Alarms/LowSoc'] = 
#        self._dbusservice['/Alarms/HighChargeCurrent'] = 
#        self._dbusservice['/Alarms/HighDischargeCurrent'] = 
#        self._dbusservice['/Alarms/CellImbalance'] = 
#        self._dbusservice['/Alarms/InternalFailure'] = 
#        self._dbusservice['/Alarms/HighChargeTemperature'] = 
#        self._dbusservice['/Alarms/LowChargeTemperature'] = 
#        self._dbusservice['/Alarms/HighTemperature'] = 
#        self._dbusservice['/Alarms/LowTemperature'] = 
       # cell voltages
       voltage_sum = 0
       for i in range(self.number_of_cells):
          cellpath = '/Voltages/Cell' + str(i+1)
          voltage_sum = voltage_sum + self.cell_volt[i]  
          self._dbusservice[cellpath] = self.cell_volt[i]
       self._dbusservice['/Voltages/Sum'] = voltage_sum
       self._dbusservice['/Voltages/Diff'] = self.cell_now_max_voltage - self.cell_now_min_voltage     
       # increment UpdateIndex - to show that new data is available
       index = self._dbusservice['/UpdateIndex'] + 1  # increment index
       if index > 255:   # maximum value of the index
         index = 0       # overflow from 255 to 0
       self._dbusservice['/UpdateIndex'] = index
       #update lastupdate vars
       self._lastUpdate = time.time() 
    except (ValueError, requests.exceptions.ConnectionError, requests.exceptions.Timeout, ConnectionError, requests.exceptions.JSONDecodeError):
       logging.info('Error getting data from BMS - check network or BMS status. Setting power values to 0')
       if ((time.time() - self._lastUpdate) > 60):    
         logging.info("-- shut down BMS") 
         logging.info((time.time() - self._lastUpdate))
       return True        
    except Exception as e:
       logging.critical('Error at %s', '_update_', exc_info=e)
       return True
       
    # return true, otherwise add_timeout will be removed from GObject - see docs http://library.isr.ist.utl.pt/docs/pygtk2reference/gobject-functions.html#function-gobject--timeout-add
    return True
 
  def _handlechangedvalue(self, path, value):
    logging.debug("someone else updated %s to %s" % (path, value))
    return True # accept the change
 


def main():
  #configure logging

  log_rotate_handler = TimedRotatingFileHandler("%s/current.log" % (os.path.dirname(os.path.realpath(__file__))),
                                     when="d",
                                     interval=1,
                                     backupCount=7)
                                     
  logging.basicConfig(format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.INFO,
        handlers=[
        logging.StreamHandler(),
        log_rotate_handler
    ])

  try:
      logging.info("Start");
  
      from dbus.mainloop.glib import DBusGMainLoop
      # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
      DBusGMainLoop(set_as_default=True)
     
      #formatting 
      _kwh = lambda p, v: (str(round(v, 2)) + ' KWh')
      _a = lambda p, v: (str(round(v, 1)) + ' A')
      _ah = lambda p, v:(str(round(v, 0)) + ' Ah')
      _w = lambda p, v: (str(round(v, 1)) + ' W')
      _v = lambda p, v: (str(round(v, 1)) + ' V') 
      _pr = lambda p , v:(str(round(v, 0)) + ' %')  
     
      #start our main-service
      bms_output = DbusJSONBMSService(
        servicename='com.victronenergy.battery',
        deviceinstance=40
        )
     
      logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
      mainloop = gobject.MainLoop()
      mainloop.run()            
  except Exception as e:
    logging.critical('Error at %s', 'main', exc_info=e)
if __name__ == "__main__":
  main()
