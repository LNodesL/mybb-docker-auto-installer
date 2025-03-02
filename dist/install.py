import os
import subprocess
import socket
import time
import random

# Define paths for local Docker and Docker Compose binaries
DOCKER_BIN = "./docker"
DOCKER_COMPOSE_BIN = "./docker-compose"
DOCKER_COMPOSE_FILE = "docker-compose.yml"
MYBB_DIR = "./mybb"
NGINX_DIR = "./nginx"
POSTGRES_DIR = "./mysql/data"

# Docker mirrors 
DOCKER_MIRRORS = [
    "docker.io",  # Default Docker registry
    "registry-1.docker.io",
    "mirror.gcr.io",
]

# Check and download Docker if missing
def check_and_install_docker():
    if not os.path.isfile(DOCKER_BIN):
        print("Docker not found locally. Downloading Docker...")
        docker_url = "https://download.docker.com/linux/static/stable/x86_64/docker-20.10.24.tgz"
        try:
            subprocess.run(f"curl -L {docker_url} -o docker.tgz", shell=True, check=True)
            subprocess.run("tar xzvf docker.tgz --strip 1 -C . && rm docker.tgz", shell=True, check=True)
            os.rename("./docker", DOCKER_BIN)
            os.chmod(DOCKER_BIN, 0o755)
            print("Docker downloaded and set up locally.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to download Docker: {e}")
            exit(1)
    else:
        print("Docker is available locally.")

# Check and download Docker Compose if missing
def check_and_install_docker_compose():
    if not os.path.isfile(DOCKER_COMPOSE_BIN):
        print("Docker Compose not found locally. Downloading Docker Compose...")
        compose_url = "https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-linux-x86_64"
        try:
            subprocess.run(f"curl -L {compose_url} -o {DOCKER_COMPOSE_BIN}", shell=True, check=True)
            os.chmod(DOCKER_COMPOSE_BIN, 0o755)
            print("Docker Compose downloaded and set up locally.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to download Docker Compose: {e}")
            exit(1)
    else:
        print("Docker Compose is available locally.")

# Check Docker and Docker Compose versions
def check_versions():
    try:
        print("\nDocker Version:")
        subprocess.run([DOCKER_BIN, "--version"], check=True)
        print("\nDocker Compose Version:")
        subprocess.run([DOCKER_COMPOSE_BIN, "--version"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error checking versions: {e}")
        exit(1)

# Create necessary directories
def create_directories():
    os.makedirs(MYBB_DIR, exist_ok=True)
    os.makedirs(NGINX_DIR, exist_ok=True)
    os.makedirs(POSTGRES_DIR, exist_ok=True)

# Generate nginx/default.conf
def generate_nginx_config():
    nginx_config = """
server {
    listen 80;
    server_name localhost;

    root /var/www/html;
    index index.php index.html index.htm;

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ \.php$ {
        include fastcgi_params;
        fastcgi_pass mybb:9000;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        fastcgi_index index.php;
    }

    location ~ /\.ht {
        deny all;
    }
}
"""
    with open(f"{NGINX_DIR}/default.conf", "w") as f:
        f.write(nginx_config)

# Find an available port
def find_available_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port

# Generate docker-compose.yml using mirrors
def generate_docker_compose(port, mirror):
    docker_compose = f"""
version: '3.8'

services:
  mybb:
    image: {mirror}/mybb/mybb:latest
    volumes:
      - {MYBB_DIR}:/var/www/html:rw

  nginx:
    image: {mirror}/library/nginx:mainline-alpine
    ports:
      - "{port}:80"
    volumes:
      - {NGINX_DIR}:/etc/nginx/conf.d:ro
      - {MYBB_DIR}:/var/www/html:ro

  mysql:
    image: {mirror}/library/mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: rootpassword123
      MYSQL_DATABASE: mybb_db
      MYSQL_USER: mybb_user
      MYSQL_PASSWORD: mybb_password123
    command: --default-authentication-plugin=mysql_native_password
    volumes:
      - ./mysql/data:/var/lib/mysql:rw
"""
    with open(DOCKER_COMPOSE_FILE, "w") as f:
        f.write(docker_compose)

# Run docker-compose with sequential mirror attempts
def run_docker_compose(port):
    print("Starting MyBB setup using Docker Compose...")
    retries = 3
    attempts = 0
    used_mirrors = set()
    
    while attempts < retries:
        # Get available mirrors that haven't been used in this attempt
        available_mirrors = [m for m in DOCKER_MIRRORS if m not in used_mirrors]
        
        if not available_mirrors:
            print("All mirrors attempted. Starting new retry cycle...")
            used_mirrors.clear()
            available_mirrors = DOCKER_MIRRORS
            time.sleep(60)  # Wait 60 seconds before retrying the same mirrors
            attempts += 1
            continue
            
        # Randomly select a mirror from available ones
        mirror = random.choice(available_mirrors)
        used_mirrors.add(mirror)
        
        print(f"Trying mirror: {mirror}")
        generate_docker_compose(port, mirror)
        
        try:
            subprocess.run([DOCKER_COMPOSE_BIN, "up", "-d"], check=True)
            time.sleep(10)
            return  # Exit if successful
        except subprocess.CalledProcessError as e:
            if "toomanyrequests" in str(e):
                print(f"Rate limit hit for mirror {mirror}. Trying next mirror...")
            else:
                print(f"Error starting containers: {e}")
            
            if available_mirrors:  # If there are more mirrors to try
                time.sleep(5)  # Wait 5 seconds before trying next mirror
    
    print("All mirrors failed. Please try again later.")

# Get server's public IP
def get_public_ip():
    try:
        # Get IPv4 address using ip command
        cmd = "ip -4 addr show scope global | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}' | head -n1"
        public_ip = subprocess.check_output(cmd, shell=True).decode().strip()
        return public_ip
    except:
        return "localhost"

# Display installation links
def display_links(port):
    public_ip = get_public_ip()
    print("\nMyBB is now running!")
    print(f"Access it via:\n- http://{public_ip}:{port}/\n- http://localhost:{port}/\n")
    print("\nMySQL Database Credentials:")
    print("Host: mysql")
    print("Database: mybb_db")
    print("Username: mybb_user")
    print("Password: mybb_password123")
    print("\nRoot Password: rootpassword123")

# Clean up function if script fails
def clean_up():
    print("Cleaning up...")
    if os.path.exists(DOCKER_COMPOSE_FILE):
        os.remove(DOCKER_COMPOSE_FILE)
    subprocess.run([DOCKER_COMPOSE_BIN, "down"], check=False)

# Main function
def main():
    try:
        check_and_install_docker()
        check_and_install_docker_compose()
        check_versions()
        create_directories()
        generate_nginx_config()
        port = find_available_port()
        run_docker_compose(port)
        display_links(port)
    except Exception as e:
        print(f"Error: {e}")
        clean_up()

# Run main function
if __name__ == "__main__":
    main()
