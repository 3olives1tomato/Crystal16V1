# Crystal16 V1

## System specifications
The software was developed for a windows operating system. The Crystal16 is connected to the PC through serial port “COM1”.

## Description
This custom software was made in order to assist experimentalist and give a second life to an old and no longer supported equipment. The motivation behing creating this software was to surpass the limitations of the official software which required the PC date to be set to a past year, to calibrate the temprature reading of each block and to be able to conduct multi-step experiments in all reactor blocks.

## Notes on the software
As this is a custom software in progress, there are a few points that can be improved for the code to be more robust and easy to use, like error handling etc. Some key guidlines to use the software are summarised below.

- [ ] The tune step must be after a temperature relevant step. If there isn't, there will be no error but the temperature of the blocks won't change. 
- [ ] There is a memory limitation of the device as per the number of recipe steps it can save at once. If that limit is exceeded, there is an “Insufficient memory” error.
- [ ] To deal with the memory limitations, the algorithm sends the recipe in batches, stopping and clearing the memory at the end of each batch.
- [ ] The stopping of the temprature control results in the reactor block temperature changing towards the temperature of the cooling water that continues to run throught the device so the user should plan the break point accordingly.
- [ ]  _get_device_info_ function should not be removed from the beginning of the code, as this leads to errors. 
- [ ] A small time slot is required between writting commands, an “Unknown parameter” error is encountered. 
- [ ] After encountering an error the program should be restarted as it may skip recipe steps or not set the gains correctly

## Recipe template .csv file
Both code files take as input a “recipe” file which contains the information for the temperature and stiring profile of the reactors and it is to be used with this format. Some general notes on this file are the following.
- [ ] The python file _Crystal16V1.9_AllBlocks_ takes as input a file named _Recipe_common.csv_ and python file _Crystal16V1.9_ takes as input 4 files named _Recipe_A.csv, Recipe_B.csv, Recipe_C.csv, Recipe_D.csv_ for each reactor block respectively.
- [ ] The tuning step is necessary for the code to run without errors and it set the transmissivity to 100%, thus in the standard case, it is good practice to tune after complete dissolution.

## License

[MIT](https://choosealicense.com/licenses/mit/)
