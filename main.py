import discord
import random

client = discord.Client()

# Dictionary so you can give it a guild and it will return the game active in that server (if there is one)
games = dict()

# Dictionary so you can give it a user and it will give you the game that contains that player (if the player is in an active game)
activePlayers = dict()

help = """!totpal is the master command. Follow it by at least 4 mentions to start a game, or follow it by a flag to issue it other commands

valid flags:
    -h or --help lists the functions of this bot and how to use it
    -cg or --cleargame clears the current active game in this server (this happens automatically at the end of a game, but this flag is if it gets stopped up somewhere)
    -i or --instructions to get instructions on how to play the game
            
Once you start a game, the bot will direct message the contestants asking for their articles. They should reply with only the title of the article, not a link.
If any of the contestants do not have direct messages enabled for the server, the bot will freeze up and you will need to clear the game before starting again.
            
Once the guesser is ready to guess, they guess by putting a message in the chat, starting with !Guess and tagging the person they are guessing."""

instructions = """**Core rules** (how the game has to work):
There is one guesser
There are three or more contestants
The guesser should be whoever you tag first when starting a game, but that cannot be guaranteed

Each of the contestants has to pick a wikipedia article. This bot will pick one of the articles at random, and it is then every contestant's job to convince the guesser that it is their article.
The contestant whose article it actually is does this by listing facts from the article. The other contestants do this buy making up plausible sounding nonsense.

At the end of questioning, the guesser will guess whose article it is. If they guess correctly, both themself and whoever they picked win. If they guess incorrectly, the person they picked wins.



**Optional rules** (the game can be run other ways but we find this works best):
Don't pick an article that both you and the guesser know about. This is a good strategy for victory but leads to short rounds that aren't fun for anybody.
Pick a random article. The desktop version of wikipedia has a random article button, keep hitting that until you find something you like.
As guesser, go to each person and get the very basics of what it is before interrogating more thoroughly."""

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):

    # So the bot never replies to its own messages
    if message.author == client.user:
        return
    # Handle the messages that start with totpal
    if message.content.lower().startswith('!totpal'.lower()):
        mentions = message.mentions

        # spins off into handleFlags if there are flags in the message
        if len(mentions) == 0 and '-' in message.content:
            await handleFlags(message)
            return

        # Don't let a game start in a server that already has one
        if message.guild in games.keys():
            await message.channel.send("Only one game can be active in a server at a time")
            return

        # Don't let a game start if a player is active in another game (could cause issues with getting article name from player)
        for mention in mentions:
            if mention in activePlayers.keys():
                await message.channel.send('Error: cannot start a game with a player active in another game')
                return

        # Don't let a game start with fewer than 4 people
        if len(mentions) < 4:
            await message.channel.send('Error: game requires at least 4 players: 1 guesser and 3 liars.')
            await message.channel.send('Please format as \"!totpal [tag guesser] [tag players]\"')
            await message.channel.send('(Note: sometimes the discord api will send us the mentions in the wrong order, '
                                       'so the wrong person may end up guesser. There isn\'t anything we can do about this.)')
            return

        # separate the guesser from the liars
        guesser = mentions[0]
        liars = mentions[1:]

        # set up game
        channel = message.channel
        game = Game(guesser, liars, channel)
        games[message.guild] = game
        activePlayers[guesser] = game
        for liar in liars:
            activePlayers[liar] = game
            # send request for article to liars
            await liar.send("Please reply with the title of your wikipedia article (not a link to it)")
        await message.channel.send ("waiting on players to reply with their articles")
        return

    # get guesses from liars
    if message.author.dm_channel is None and message.channel == message.author.dm_channel:
        liar = message.author
        if not liar in activePlayers.keys():
            return;
        await activePlayers[liar].addArticle(liar, message.content)

    # get the guess from the person
    if message.content.lower().startswith('!Guess'.lower()):
        await handleGuess(message)

# responds to any flags in the message
async def handleFlags(message):
    hasFlags = False
    if '-cg' in message.content.lower() or '--cleargame' in message.content.lower():
        clearGame(message.guild)
        await message.channel.send('Game Cleared!')
        hasFlags = True
    if '-h' in message.content.lower() or '--help' in message.content.lower():
        await message.channel.send(help)
        hasFlags = True
    if '-i' in message.content.lower() or '--instructions' in message.content.lower():
        await message.channel.send(instructions)
        hasFlags = True

    if not hasFlags:
        return


# handles a person guessing
async def handleGuess(message):

    if not message.author in activePlayers.keys():
        await message.channel.send('You are not in an active game, ' + message.author.display_name)
    game = activePlayers[message.author]
    if message.author != game.guesser:
        await message.channel.send('You are not the guesser, ' + message.author.display_name)
    guess = message.mentions[0]
    if guess == game.SelectedLiar:
        await message.channel.send(
            'You guessed correctly! ' + game.guesser.display_name + ' and ' + game.SelectedLiar.display_name + ' win!')
    else:
        await message.channel.send(
            'You guessed incorrectly. The correct answer was ' + game.SelectedLiar.display_name + '. ' + guess.display_name + ' wins!')

    clearGame(message.guild)

# Clears the active game in the server, in case the server gets clogged up from some error
def clearGame(guild):
    if guild in games:
        game = games.pop(guild)
        activePlayers.pop(game.guesser)
        for liar in game.liars:
            activePlayers.pop(liar)


# sends the message to start the game
async def startGame(article, channel):
    await channel.send("The article is: " + article)
    await channel.send('Guess in the format "!Guess [tag your guess]')

class Game:

    def __init__(self, guesser, liars, channel):
        self.guesser = guesser
        self.liars = liars
        self.channel = channel
        self.articles = dict()
        self.gameActive = False
        for liar in self.liars:
            self.articles[liar] = ""

    # adds the article and associates it with the liar
    async def addArticle(self, liar, article):
        if not liar in self.liars:
            return
        if article in self.articles.values():
            await liar.send("Someone else has already selected this article")
            return
        self.articles[liar] = article
        if not "" in self.articles.values():
            await self.startGame()
        return

    # Starts up the game
    async def startGame(self):
        self.gameActive = True
        pair = random.sample(list(self.articles.items()), 1)
        self.SelectedLiar, self.SelectedArticle = pair[0]
        await startGame(self.SelectedArticle, self.channel)


keyFile = open('key.txt', 'r')
client.run(keyFile.read())