#!/bin/sh

# Recreate config file
rm -rf ./envConfig.js
touch ./envConfig.js

# Add assignment 
echo "window.envConfig = {" >> ./envConfig.js

# Read each line in .env file
# Each line represents key=value pairs
while IFS= read -r line || [ -n "$line" ];
do
  # Split env variables by character `=`
  if printf '%s\n' "$line" | grep -q -e '='; then
    varname=$(printf '%s\n' "$line" | cut -d'=' -f1 | tr '[:lower:]' '[:upper:]')
    varvalue=$(printf '%s\n' "$line" | cut -d'=' -f2-)
  fi

  # Read value of current variable if exists as Environment variable
  eval "value=\$$varname"
  # Otherwise use value from .env file
  [ -z "$value" ] && value="$varvalue"
  
  # Append configuration property to JS file
  echo "  $varname: \"$value\"," >> ./envConfig.js
done < backend.env

echo "}" >> ./envConfig.js