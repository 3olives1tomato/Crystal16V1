# Crystal16 V1

## Description
This custom software was developed to assist experimentalists and breathe new life into old, unsupported equipment. The motivation behind creating this software was to overcome the limitations of the official software. The official software required the PC date to be set to a past year to calibrate the temperature reading of each block and conduct multi-step experiments in all reactor blocks.

## System Specifications
The software was designed for a Windows operating system within a Python environment. The Crystal16 V1 is connected to the PC through the serial port “COM1.”

## Python Files
Two files are available for two operation modes:
- [ ] `_Crystal16V1.9_AllBlocks_` is used when applying the same profile to all blocks.
- [ ] `_Crystal16V1.9_` is used when applying independent profiles to each block.

## Recipe Template .CSV File
Both code files take a "recipe" file as input, containing information for the temperature and stirring profile of the reactors. Some general notes on this file are as follows:
- [ ] The Python file `_Crystal16V1.9_AllBlocks_` takes as input a file named `_Recipe_common.csv_`. The Python file `_Crystal16V1.9_` takes as input four files named `_Recipe_A.csv, Recipe_B.csv, Recipe_C.csv, Recipe_D.csv_` for each reactor block, respectively.
- [ ] The tuning step is necessary for the code to run without errors, and it sets the transmissivity to 100%. In the standard case, it is good practice to tune after ensuring complete dissolution.

## Notes on the Software
As this is a custom software in progress, there are a few points that can be improved for the code to be more robust and easy to use, such as error handling, etc. Some key guidelines to use the software are summarized below:

- [ ] The tune step must follow a temperature-relevant step. If it doesn't, there will be no error, but the temperature of the blocks won't change.
- [ ] There is a memory limitation on the device concerning the number of recipe steps it can save at once. If that limit is exceeded, an "Insufficient memory" error will occur.
- [ ] To deal with memory limitations, the algorithm sends the recipe in batches, stopping and clearing the memory at the end of each batch.
- [ ] The stopping of temperature control results in the reactor block temperature changing towards the temperature of the cooling water that continues to run through the device. Therefore, the user should plan the break point accordingly.
- [ ] The `_get_device_info_` function should not be removed from the beginning of the code, as its absence leads to errors.
- [ ] A small time slot is required between writing commands; otherwise, an "Unknown parameter" error is encountered.
- [ ] After encountering an error, the program should be restarted as it may skip recipe steps or not set the gains correctly.

## License
[MIT](https://choosealicense.com/licenses/mit/)

