# About
This program automatically checks you into an iClicker course. Just keep the program running. You need to have Google Chrome or the Chromium WebDriver installed. This is not a script or extension; this opens a webbrowser, logs into iClicker, and waits until the Join Meeting prompt appears.

## Why make this

Because iClicker isn't fun to check-in for attendance. That's it tbh. I can't really justify it beyond this.

Also, I wanted something to try out Selenium on. 

# Requirements

* Python. You can install it [here](https://www.python.org/downloads/).
* Selenium and Selenium-wire python packages. You can install via pip using

  ```
  pip install selenium-wire selenium
  ```
* [Google Chrome](https://www.google.com/chrome/) or the [Chrome WebDriver](https://sites.google.com/chromium.org/driver/) installed.
* A `config.json` file in the running directory. It should be formatted like this:

  ```json
  {
    "Account name":
    {
      "Email": "myemail@email.com",
      "Password": "mypassword123",
      "Courses":
        {
        "Course 1 name": 
        {
          "Name": "Course 1 name",
          "Start Time": "21:30",
          "End Time": "22:50"
        },
        "Course 2 name": 
        {
          "Name": "Course 2 name",
          "Start Time": "8:30",
          "End Time": "11:20"
        }
        }
    }
  }
  ```
    *The `Course name` value should be the name exactly as it is in iClicker*
    
    *Except for `Account name` and individual course keys, no key names should be adjusted*
    
    *The times should be in 24-hour format and based off of UTC time*

    *Do not make End Time overlap with another Start Time (e.g., Course 1 has End Time of 22:50 and Course 2 has Start Time of 22:50)* 

# Usage

Import `iClicker_driver` into your code using
  ```python
  from iClicker_driver import iClicker_driver
  ```

Then create an iClicker_driver object. Optional arguments include
* `config_file` - The filename of the *.json* which contains all the account and course information. Default is `config.json`
* `auto_wait` - A boolean that defines whether the object should automatically wait for the meeting to start upon entering a course. Default is `True`

Call `start()` to set up the WebDriver and log-in. You should be prompted for an account name, which should be the `Account name` in the *.json* config file (e.g., "Account name" as it is in the above example).

# To-do

* Implement adjustment of geolocation.
