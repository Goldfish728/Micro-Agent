# Use an official Python runtime as a parent image 
FROM python:3.9-slim 
 
# Set the working directory in the container 
WORKDIR /app 
 
# Copy the current directory contents into the container at /app 
COPY . /app 
 
# Install any needed packages specified in requirements.txt 
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
 
# Make port 5000 available to the world outside this container 
EXPOSE 8000
 
# Run app.py when the container launches 
CMD ["python", "-m", "http.server", "8000"] 
