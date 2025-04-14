Design Considerations / FAQ
-------------------
| Due to the sort of spread out way that this library is set up, the nature of scripting work, and the fact that I am not a professional programmer, there are some decisions I make that are not self-evident and potentially not pythonic.   
| When I make these decisions I will try and post them here. If you come across a decsion like this please complain, and it will end up here. 

1. Importing ENV and config files
I have decided to keep env files and configs separate.  Functions don't really care where they come from, and variable names are lower case where env variables are upper case  
So i have decided to hard-code env variables as upper case, config as lower case, and if need both i can then import both into the function like so:    

.. code-block:: python

   func(**config, **os.environ)

This means that env-type variables like usernames and passwords are upper case! Could be a gotcha. They will also be documented in the function

