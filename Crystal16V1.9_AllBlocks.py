import serial
from datetime import datetime
from datetime import timedelta as deltat
import time
import pandas as pd
import os
import threading
import numpy as np
from copy import deepcopy
from math import ceil
from operator import itemgetter
import tkinter as tk


class Crystal16:
    def __init__(self, port, baudrate=9600):
        self.all_data, self.RBs, self.total_time_min,\
            self.version, self.date_time, self.total_duration_min, self.recipe_commands_batches, self.total_times_RB= \
            pd.DataFrame([]), [], [0,0,0,0], [], [], None, [0,0,0,0], [0,0,0,0] # Initialize global variables
        self.sample_rate=50 # Set sample rate for writing data to the csv
        self.n_max_steps= 14 # Set max length of recipe steps writen at once in each block, limited by the Crystal16 V1 memory
        self.DeltaT= {'0':(0,0), '1':(0,0), '2':(0.01,-1.07), '3':(0.02,-1.40)} # Temperature correction factors for each block
        # DeltaT= T_targ - T_in 
        # DeltaT=a*T_targ + b
        # T_in= (1-a)T_targ-b --- what to input as command
        # T_act= (1+a)T_out+b --- what to read from device
        
        self.disable_measurement=False # Enable data logging

        print("Enter filename.")
        self.filename = input()
        # Specify directories and experiment details
        print("Enter directory to save results in.")
        self.save_directory= input()
        print("Enter directory of recipe file.")
        self.recipe_directory= input()

        self.get_experiment_description()
        
        self.ser = serial.Serial(port, baudrate, timeout=1) # Open serial connection        
        self.get_device_info() # Setup equipment before starting logging 
        
        self.event = threading.Event()
        self.lock = threading.Lock()
      
     
     #  ___       _ _   _       _ _          _   _             
     # |_ _|_ __ (_) |_(_) __ _| (_)______ _| |_(_) ___  _ __  
     #  | || '_ \| | __| |/ _` | | |_  / _` | __| |/ _ \| '_ \ 
     #  | || | | | | |_| | (_| | | |/ / (_| | |_| | (_) | | | |
     # |___|_| |_|_|\__|_|\__,_|_|_/___\__,_|\__|_|\___/|_| |_|
         
    def get_device_info(self): # Also write this information in the .csv file     
        self.ser.write('version\r\n'.encode()) 
        self.ser.write('serial\r\n'.encode())
        self.ser.write('time\r\n'.encode()) 
        
        self.disable_measurement =True # Disable logging to read
        byte_string=self.ser.read(100000) 
        self.disable_measurement=False # Enable logging again

        # Read device info
        if  b'version' in byte_string:
            byte_substring=byte_string.partition(b'version')[-1]
            version=byte_substring.partition(b'ao')[0]
            self.version=version.decode()
            print('\n Version:',self.version ,'\n')
                
        if  b'serial' in byte_string:
            byte_substring=byte_string.partition(b'serial')[-1]
            serial=byte_substring.partition(b'=')[0]
            print('\n Serial number:', serial.decode(),'\n')
         
        if  b'time' in byte_string:
            byte_substring=byte_string.partition(b'time')[-1]
            date_time=byte_substring.partition(b'=')[0]
            self.date_time=date_time.decode()
            print('\n Time is:',self.date_time ,'\n')
            
    def get_experiment_description(self):
        
        def save_text():
            text_input = text_box.get("1.0", tk.END).strip()  # Get the text from the text box
            self.experiment_description = '\n'.join(text_input.splitlines())  # Store the text, separating each line
            window.destroy()  # Close the window

        # Create a Tkinter window
        window = tk.Tk()
        window.title("Enter experiment description")
        window.geometry("400x200")  # Set the window size (width x height)

        # Create a text box
        text_box = tk.Text(window, height=5, width=30)
        text_box.pack()

        # Create a button to save the text
        button = tk.Button(window, text="Save", command=save_text)
        button.pack()

        # Start the Tkinter event loop
        window.mainloop()
    
     #  _                      _             
     # | |    ___   __ _  __ _(_)_ __   __ _ 
     # | |   / _ \ / _` |/ _` | | '_ \ / _` |
     # | |__| (_) | (_| | (_| | | | | | (_| |
     # |_____\___/ \__, |\__, |_|_| |_|\__, |
     #             |___/ |___/         |___/ 
        
    def enable_logging(self):
        self.ser.write('log on\r\n'.encode())
        
    def disable_logging(self):
        self.ser.write('log off\r\n'.encode())
        
    def log_data(self):         
        self.CurrentTime, self.TimerStamp, self.Temperatures,\
            self.Transmissivities, self.DuePoint, self.Humidity =[], [], [], [], [], [] # Initialize variables to write

        self.enable_logging() # Open data transmission from device
        self.job_thread = threading.Thread(target=self.get_response, daemon=True)
        self.job_thread.start() #Start logging
        self.time_zero = datetime.now() # Begin timer when the logging starts
        print('Starting logging\n')
        
    def get_response(self):
        response = [] # Clear every time the function is called
        while not self.disable_measurement:
            try:
                response = self.ser.readline().decode()
                if response[0] == ">": # Fix lines starting with ">"
                    response = response[1:]
                response = response.strip('\r\n')
                if response[0:len(":get ai")] == ":get ai":
                    data_batch=[]
                if response[0] == ":": # Append only valid communications
                    data_batch.append(response)
                if response[0:len(":stat end")] == ":stat end" and data_batch[0][0:len(":get ai")]== ":get ai": # If there is a complete data log, append and process response                 
                    self.process_response(data_batch)                               
                if response.startswith(':error'): # Check for errors and print
                    print('Error encountered \nTerminating program...\n')   
                    print(response)
                    self.close_and_save()                    
            except:
                #print("Could not read from device")
                pass
                
    def process_response(self,data_batch):              
        # Dictionary of parameters
        # ai: transmissivity measurements, pt: reactor block and ambient temperatures,
        # hu: humidity, dp: due point, ao: analog output
        device_measurements = {'ai': 0, 'pt':1, 'hu':2, 'dp':3, 'ao': 4, 'so':5, 'tf':6, 'ad':7}  
        
        hu, dp, temps_ar, trans_ar =[], [], [], [] # Clear variables for each data batch
               
        time_now=datetime.now() # Get time
        duration = (time_now - self.time_zero).total_seconds() # Calculate elapsed time in seconds since beggining of logging     
        
        for info in data_batch:            
            if 'hu' in info: # Get humidity
                subinfo=info.partition('0')[-1]
                hu=subinfo.partition('=')[0]
                hu=float(hu)
                # print('Humidity is', hu,'%\n')            
            
            if 'dp' in info: # Get dew point
                subinfo=info.partition('1')[-1]
                dp=subinfo.partition('0.0')[0]
                dp=float(dp)
                # print('The dew point is', dp,'°C\n')
                               
            if 'pt' in info: # Get reactor block and ambient temperature 
                subinfo=info.partition('4')[-1]
                temps=subinfo.partition('=')[0]       
                temps=temps.split()
                temps_ar=[float(i) for i in temps]
                # print('\nReactor block temperatures are:',temps_ar[0:-1] ,'°C\n')
                # print('Temperature is:', [float(temps_ar[-1])],'°C\n')       
                       
            if 'ai' in info: # Get transmissivities
                subinfo=info.partition('15')[-1]
                trans=subinfo.partition('=')[0]
                trans=trans.split()
                trans_ar=[int(i) for i in trans]
                # print(f'Transmissivities are:{trans_ar}\n')
         
        # Append data to global variables 
        self.CurrentTime.append(time_now.strftime('%m-%d-%Y %H:%M:%S'))
        self.TimerStamp.append(str(deltat(seconds=np.round(duration))))      
        self.Temperatures.append(temps_ar)
        self.Transmissivities.append(trans_ar)
        self.DuePoint.append(dp)
        self.Humidity.append(hu)
       
        if len(self.Temperatures)>=self.sample_rate: # Write to .csv after every x readings
            self.save_to_file()  
               
    def save_to_file(self):  
        # Organize data in data frames
        #  Temperature dependent correction factors for the target temperature vs Tactual          
        DeltaT = self.DeltaT  # DeltaT= a*Tout + b -> (a,b)
        Temperatures=[]
        for RB in ['0','1','2','3']:
            temperatures=list( map(itemgetter(int(RB)), self.Temperatures ))
            a,b= DeltaT[RB]                
            Temperatures.append([(1+a)*temp+b for temp in temperatures ])
        
        data_frame_output = {'Time': self.CurrentTime, 'Decimal Time [hh:mm:ss]': self.TimerStamp,\
                                  'Block A Actual Temperature [°C]': Temperatures[0],\
                                  'Block B Actual Temperature [°C]': Temperatures[1],\
                                  'Block C Actual Temperature [°C]': Temperatures[2],\
                                  'Block D Actual Temperature [°C]': Temperatures[3],\
                                  'A1 Transmissivity [%]': list( map(itemgetter(0), self.Transmissivities )), 'A2 Transmissivity [%]': list( map(itemgetter(1), self.Transmissivities )),\
                                  'A3 Transmissivity [%]': list( map(itemgetter(2), self.Transmissivities )), 'A4 Transmissivity [%]': list( map(itemgetter(3), self.Transmissivities )),\
                                  'B1 Transmissivity [%]': list( map(itemgetter(4), self.Transmissivities )), 'B2 Transmissivity [%]': list( map(itemgetter(5), self.Transmissivities )),\
                                  'B3 Transmissivity [%]': list( map(itemgetter(6), self.Transmissivities )), 'B4 Transmissivity [%]': list( map(itemgetter(7), self.Transmissivities )),\
                                  'C1 Transmissivity [%]': list( map(itemgetter(8), self.Transmissivities )), 'C2 Transmissivity [%]': list( map(itemgetter(9), self.Transmissivities )),\
                                  'C3 Transmissivity [%]': list( map(itemgetter(10), self.Transmissivities )), 'C4 Transmissivity [%]': list( map(itemgetter(11), self.Transmissivities )),\
                                  'D1 Transmissivity [%]': list( map(itemgetter(12), self.Transmissivities )), 'D2 Transmissivity [%]': list( map(itemgetter(13), self.Transmissivities )),\
                                  'D3 Transmissivity [%]': list( map(itemgetter(14), self.Transmissivities )), 'D4 Transmissivity [%]': list( map(itemgetter(15), self.Transmissivities ))}
        
        df = pd.DataFrame(data_frame_output)
        
        self.all_data = pd.concat([self.all_data, df]) # Save all log data in global variable 
        self.all_data.reset_index(drop=True, inplace=True) # Renew dataframe indices
        
        self.CurrentTime, self.TimerStamp, self.Temperatures,\
            self.Transmissivities, self.DuePoint, self.Humidity =[], [], [], [], [], [] # Clear variables after saving
                       
        all_data=self.all_data
        filename_csv= self.filename + '.csv'
        os.chdir(self.save_directory) # Set working directory to save the .csv file
        try:
            all_data.to_csv(filename_csv, index=False) # Renew the csv file with all the data gathered, every x measurements
        except PermissionError: # if the file is already open and it fails to log the data, create new file 
            filename_auto='Autosave_'+ filename_csv
            all_data.to_csv(filename_auto, index=False)
                                    
    def save_temperature_profile(self, RB, recipe_matrix):
        
        ## Process data and complete table to print
    
        # Temperature 
        
        while '' in recipe_matrix[1]:
            recipe_matrix[1] =[ recipe_matrix[1][i-1]  if recipe_matrix[0][i]=='tune' or recipe_matrix[0][i]=='stir' \
                           else recipe_matrix[1][i] for i in range(len(recipe_matrix[4]))] # Complete the column
          
        # Rate
        recipe_matrix[2] = [str(float(i)*60) if i else '' for i in recipe_matrix[2]] # Convert units to °C/min
        
        # Duration 
        hold_dur = [str(float(i)/60) if i else '' for i in recipe_matrix[3]] # Convert units to min
           
        ramp_dur = [str(abs(float(recipe_matrix[1][i]) - float(recipe_matrix[1][i-1]))/ float(recipe_matrix[2][i]) )\
                            if recipe_matrix[2][i]!='' else 0 for i in range(len(recipe_matrix[3]))]
        recipe_matrix_dur = [hold_dur[i] if hold_dur[i] != '' else ramp_dur[i] for i in range(len(hold_dur))] # Complete the column
        recipe_matrix[3]=recipe_matrix_dur
   
        # Stirring speeds
        while '' in recipe_matrix[4]:
            recipe_matrix[4] = [recipe_matrix[4][i] if recipe_matrix[4][i]\
                                else recipe_matrix[4][i-1] for i in range(len(recipe_matrix[4]))] # Complete the column
        
        # Total times
        total_time_min=np.cumsum([float(i) for i in recipe_matrix_dur])
        total_time=[str(deltat(minutes=i)) for i in np.round(total_time_min)]
        recipe_matrix.append(total_time)
                    
        headers=['Actions', 'Temperature [°C]', 'Rate [°C/min]', 'Duration [min]', 'Stiring speed [rpm]', 'Total time [H:M:S]']
        
        data_frame_recipe_matrix = {}
        for i in range(len(headers)): # Put in dataframe 
            data_frame_recipe_matrix[headers[i]] =  recipe_matrix[i]
        recipe_dataframe = pd.DataFrame(data_frame_recipe_matrix)

        recipe_dataframe.drop(recipe_dataframe[recipe_dataframe['Actions'] == 'stir'].index, inplace = True) # Remove the stir steps to print
        recipe_dataframe.reset_index(drop=True, inplace=True) # Renew dataframe indices
        
        #  Save recipe info in csv
        os.chdir(self.save_directory) # Set working directory to save the .csv file
        filename=f'Recipe_{self.filename}.csv'
         
        device_info = [
            'Data Report File: '+str(self.version),           
            'Start of Experiment: '+str(self.date_time), '',          
            'Description: ',
            self.experiment_description, '',
            'Temperature Program','']

        with open(filename, 'w') as file:
            for info in device_info:
                file.write(info + '\n')
                
        try:
            recipe_dataframe.to_csv(filename, mode='a', index=False) # Append the DataFrame to the file
        except PermissionError: # if the file is already open and it fails to log the data, create new file 
            filename=f'Autosave_Recipe_{self.filename}_common.csv'
            recipe_dataframe.to_csv(filename, header='column_names',index=False)  
            
        return total_time_min # return total times of batches

    def close_and_save(self):    
        self.stop_recipe('all') # stop and clear recipe in all blocks
        self.clear_recipe('all') 
        self.disable_measurement=True # stop logging 
        self.disable_logging() # stop readings transmission from the Crystal16 V1
        self.ser.close() # close port
        if self.Temperatures:
            self.save_to_file() # save data   
        
        try:
            self.job_thread.join()
        except:
            pass

#   _____      _   _   _                 
#  / ____|    | | | | (_)                
# | (___   ___| |_| |_ _ _ __   __ _ ___ 
#  \___ \ / _ \ __| __| | '_ \ / _` / __|
#  ____) |  __/ |_| |_| | | | | (_| \__ \
# |_____/ \___|\__|\__|_|_| |_|\__, |___/
#                               __/ |    
#                              |___/        
   
    def set_gains(self, RBs):
        # Dictionary of parameters and actions 
        gain_actions= {0:'tune', 1:'set'   , 2:'set'   , 3:'set'   } 
        gain_settings={0:''    , 1:'p_gain', 2:'i_gain', 3:'d_gain'}
        gain_values=  {0:'200' , 1:'900'   , 2:'70'    , 3:'6000'  }
                
        set_gains_commands=[]
        for RB in RBs: # Form commands
            for col in range(len(gain_actions)):
                ingredients = [gain_actions[col], gain_settings[col], RB, gain_values[col] ]  
                set_gains_commands.append(f"{' '.join([ingredient for ingredient in ingredients if ingredient != ''])}\r\n")             
        for command in set_gains_commands:
            time.sleep(1)            
            self.ser.write(command.encode()) # Write commands with time slot
            print('Write command: ',command)
        time.sleep(1)    
        print(f'Gains set in all reactors\n')

 #  _______                                  _                    _____                                     
 # |__   __|                                | |                  |  __ \                                    
 #    | | ___ _ __ ___  _ __   ___ _ __ __ _| |_ _   _ _ __ ___  | |__) | __ ___   __ _ _ __ __ _ _ __ ___  
 #    | |/ _ \ '_ ` _ \| '_ \ / _ \ '__/ _` | __| | | | '__/ _ \ |  ___/ '__/ _ \ / _` | '__/ _` | '_ ` _ \ 
 #    | |  __/ | | | | | |_) |  __/ | | (_| | |_| |_| | | |  __/ | |   | | | (_) | (_| | | | (_| | | | | | |
 #    |_|\___|_| |_| |_| .__/ \___|_|  \__,_|\__|\__,_|_|  \___| |_|   |_|  \___/ \__, |_|  \__,_|_| |_| |_|
 #                     | |                                                         __/ |                    
 #                     |_|                                                        |___/                                                            
        
    def make_recipes(self, RB:str):
        ReactorBlocks = {0:'A', 1:'B', 2:'C', 3:'D'}   # Reactor block dictionary 
        #  Temperature dependent correction factors for the target temperature vs Tactual          
        DeltaT = self.DeltaT  # DeltaT= a*Target_temp + b -> (a,b)
        a,b= DeltaT[RB]
        df = pd.read_csv(self.recipe_directory+'\Recipe_common.csv')        
        df = df.fillna('') # Replace nan with empty string
        # print(df)
        recipe=np.array(df.values.tolist()).T                
        action=  recipe[0]
        temperature= recipe[1]
        rate= recipe[2]
        duration= recipe[3]
        stirring_speed =[str(int(float(i))) if i else '' for i in recipe[4]] 

        rate_cal = [str(format(float(i)/60, '.3f')) if i else '' for i in rate] # Convert units to °C/sec
        duration_cal = [str(int(float(i)*60)) if i else '' for i in duration] # Convert units sec 
        # Apply temperature correction to the target temperature  
        temp_cor =[str(format((1 - a) * float(i) - b, '.1f')) if i else '' for i in temperature] # Convert units to °C/sec        
        recipe_matrix=[action, temp_cor, rate_cal, duration_cal, stirring_speed] # Gather all info for 1st cycle in a list of lists
           
        # Form commands       
        recipe_commands_RB = [] 
        for col in range(len(recipe_matrix[0])):
            ingredients = [recipe_matrix[row][col] for row in range(len(recipe_matrix))]
            recipe_commands_RB.append(f"recipe load {RB} {col} {' '.join([ingredient for ingredient in ingredients if ingredient != ''])}\r\n")               
        total_times_RB=self.save_temperature_profile(RB, recipe_matrix)
        
        self.total_duration_min=total_times_RB[-1]  # same for all blocks
        
        return recipe_commands_RB, total_times_RB
                
    def break_load_and_start_recipe(self, RBs):  
        for RB in RBs:
                recipe_commands_RB, total_times_RB = self.make_recipes(RB)                                
                self.recipe_commands_batches[int(RB)] = [recipe_commands_RB[i:i+self.n_max_steps] for i in range(0, len(recipe_commands_RB), self.n_max_steps)]
                self.total_times_RB[int(RB)] = [total_times_RB[i:i+self.n_max_steps] for i in range(0, len(total_times_RB), self.n_max_steps)]
                n_batches=len(self.recipe_commands_batches[int(RB)]) # same for all blocks
                
        for i in range(n_batches):
            print(f"Starting batch {i+1}")
            for RB in RBs:
                time.sleep(1)
                batch= self.recipe_commands_batches[int(RB)][i]  
                times= self.total_times_RB[int(RB)][i]                                 
                for k in range(len(batch)):
                    cmd_string = batch[k].split(" ")
                    cmd_string[3] = str(k)
                    cmd_string = " ".join(cmd_string)
                    batch[k] = cmd_string
                for command in batch: # Write recipe 
                    time.sleep(0.3) # Time slot between commands 
                    print('Write command: ',command)
                    self.ser.write(command.encode())
                    
            if i == 0:
                sleep_duration = times[-1]
            else:
                sleep_duration = times[-1] - self.total_times_RB[int(RB)][i-1][-1] 
                
            time.sleep(0.3)
            self.start_recipe('all') # Start all blocks 
            print(f"Duration is {format(sleep_duration/60, '.6f')} hours")
            time.sleep(sleep_duration*60 + 1) # Wait until the batch is executed (plus 1 sec), convert minutes to seconds
            self.stop_recipe('all') # Stop at the end of each batch 
            time.sleep(0.3)
            self.clear_recipe('all') # Clear at the end of each batch 
            time.sleep(0.3)
   
    def stop_recipe(self, RB:str): 
        if RB =='all':
            string='recipe stop\r\n'  # Stop all blocks
            self.ser.write(string.encode())
            print('Write command: ',string)
        else:
            string='recipe stop '+RB+'\r\n'  # Stop just block RB
            self.ser.write(string.encode())
            print('Write command: ',string)
        time.sleep(0.3)
                
    def start_recipe(self, RB:str): 
        if RB =='all':
            string='recipe start\r\n'  # Start all blocks
            self.ser.write(string.encode())
            print('Write command: ',string)
        else:
            string='recipe start '+RB+'\r\n'  # Start just block RB
            self.ser.write(string.encode())
            print('Write command: ',string)
        time.sleep(0.3)
        
    def clear_recipe(self, RB:str):
        if RB =='all':
            string='recipe clear\r\n'  # Clear all blocks
            self.ser.write(string.encode())
            print('Write command: ',string)
        else:
            string='recipe clear '+RB+'\r\n'  # Clear just block RB
            self.ser.write(string.encode())
            print('Write command: ',string)
        time.sleep(0.3)
                     
def main():
    
    C16=Crystal16('COM1')
    try:
        C16.stop_recipe('all')
        C16.clear_recipe('all')
        C16.log_data()
        RBs = ['0', '1', '2','3']
        # C16.set_gains(RBs)
        C16.break_load_and_start_recipe(RBs)
    finally:
        time.sleep(1)
        print('\nClosing and saving files..\n')      
        C16.close_and_save()

main()