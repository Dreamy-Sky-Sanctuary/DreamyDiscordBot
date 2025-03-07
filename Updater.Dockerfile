FROM ubuntu:22.04

# set the working directory
WORKDIR /DreamyDiscordBot

# Update the package list
RUN ["apt-get", "update"]

# Install git
RUN apt-get install git -y

COPY ./.gitconfig /root/.gitconfig

RUN git config --global --add safe.directory /DreamyDiscordBot

# Run the bot
CMD ["git", "pull"]
