#!/usr/bin/env python3

# import asyncio
# # import websockets
# import json
# import uuid

print("Welcome to the Game Boy Online Server!")

import json
import uuid
import asyncio
import datetime
import random
import websockets
import string
import ssl
# Global scope #YOLO
active_games = {
}

# Because Python sucks
class Game:
    pass
import time

import logging
class Client:
    STATE_ALIVE = 0
    STATE_DEAD = 1
    STATE_WINNER = 2

    def __init__(self, socket, name):
        self.game = None
        self.name = name
        self.uuid = str(uuid.uuid4())
        self.socket = socket
        self.height = 0
        self.state = self.STATE_ALIVE
        self.num_wins = 0
    
    def set_game(self, game):
        print("Setting game...")
        self.game = game

    async def process(self):
        async for msg in self.socket:
            # Maybe also should have max duration or so.. not sure.
            if self.game.state == Game.GAME_STATE_FINISHED:
                print("Game finished")
                return
            print("Await..")
            await self.game.process(self, json.loads(msg))
            print("Post process...")
    

    def set_dead(self):
        self.state = self.STATE_DEAD
    
    def set_winner(self):
        self.state = self.STATE_WINNER
        self.num_wins += 1

    async def send(self, f):
        print("Sending..")
        await self.socket.send(f)
        print("Done")
    
    def serialize(self):
        return {
            "name": self.name,
            "height": self.height,
            "state": self.state,
            "uuid": self.uuid,
            "num_wins": self.num_wins
        }

class Game:
    GAME_STATE_LOBBY = 0
    GAME_STATE_RUNNING = 1
    GAME_STATE_BETWEEN = 2
    GAME_STATE_FINISHED = 3

#    def _generate_name(self):
#        lobby_name = ''.join(random.choice(string.ascii_uppercase) for i in range(4))
#        print('lobby created with name', lobby_name)
#        return lobby_name
#
#   generate lobby name with number

    def _generate_name(self):
        # Access the global 'games' dictionary to see what is already taken
        # This works because python resolves globals at runtime
        global games 
        existing_ids = set(games.keys())

        # Tier 1: Try 0 - 99 first
        # We create a set of all numbers 0-99, then subtract existing ones
        tier1 = set(str(i) for i in range(100))
        available_tier1 = list(tier1 - existing_ids)
        
        if available_tier1:
            lobby_name = random.choice(available_tier1)
            print('lobby created with name', lobby_name)
            return lobby_name

        # Tier 2: Try 100 - 999
        tier2 = set(str(i) for i in range(100, 1000))
        available_tier2 = list(tier2 - existing_ids)
        
        if available_tier2:
            lobby_name = random.choice(available_tier2)
            print('lobby created with name', lobby_name)
            return lobby_name

        # Tier 3: Try 1000 - 9999
        tier3 = set(str(i) for i in range(1000, 10000))
        available_tier3 = list(tier3 - existing_ids)
        
        if available_tier3:
            lobby_name = random.choice(available_tier3)
            print('lobby created with name', lobby_name)
            return lobby_name

        # If we get here, the server has 10,000 active games!
        raise Exception("Server is full: No available lobby IDs.")


    def __init__(self, admin_socket):
        self.name = self._generate_name()
        self.admin_socket = admin_socket
        self.clients = [admin_socket]
        self.state = self.GAME_STATE_LOBBY
        self.preset_rng = {'garbage': None, 'pieces': None, 'well_column': None} # if None, generate using near GB RNG
    
    def get_gameinfo(self):
        users = []
        for client in self.clients:
            users.append(client.serialize())

        return {
            "type": "game_info",
            "name": self.name,
            "status": self.state,
            "users": users
        }

    async def send_lines(self, lines, sender_uuid):
        for c in self.clients:
            if c.uuid == sender_uuid:
                # Don't send lines to sender
                continue
            await c.send(json.dumps({
                "type": "lines",
                "lines": lines
            }))

    async def send_reached_30_lines(self, sender_uuid):
        for c in self.clients:
            if c.uuid == sender_uuid:
                # Don't send to sender
                continue
            print("sending reached lines")
            await c.send(json.dumps({
                "type": "reached_30_lines"
            }))

    async def send_gameinfo(self):
        for s in self.clients:
            await self.send_gameinfo_client(s)

    async def send_gameinfo_client(self, client):
        game_info = json.dumps(self.get_gameinfo())
        await client.send(game_info)


    async def send_all(self, data):
        for c in self.clients:
            # TODO: Serialized, might wanna create_task here
            await c.send(json.dumps(data))


    async def add_client(self, client):
        if self.state != self.GAME_STATE_LOBBY:
            raise("Game not in lobby")
        self.clients.append(client)
        await self.send_gameinfo()

    async def start_game(self):
        self.state = self.GAME_STATE_RUNNING
        for c in self.clients:
            c.state = Client.STATE_ALIVE
        if self.preset_rng['garbage'] is not None:
            garbage = self.preset_rng['garbage']
        else:
            garbage = Game.generate_random_garbage()
        await self.send_all({
            "type": "garbage",
            "garbage": garbage
        })
        pieces = Game.generate_pieces(256, beginning=self.preset_rng['pieces'])
        if self.preset_rng['well_column'] is not None:
            pieces = pieces[0:510] + self.preset_rng['well_column']
        await self.send_all({
            "type": "start_game",
            "tiles": pieces
        })
    
    def alive_count(self):
        count = 0
        for c in self.clients:
            if c.state == Client.STATE_ALIVE:
                count += 1
        return count

    def get_last_alive(self):
        for c in self.clients:
            if c.state == Client.STATE_ALIVE:
                return c
        return None

    # thx tolstoj
    @staticmethod
    def generate_random_garbage():
        initial_stack = ""
        tile_length = []
        current_index = 0
        #possible_minos = ["0C", "1D", "0E", "0C", "27"]
        mino_pointer = 0
        sum = 0
        while sum < 100:
            random_length = random.randint(1, 5)
            sum += random_length
            tile_length.append(random_length)
        if sum > 100:
            tile_length[-1] -= (sum - 100)
        for i in range(len(tile_length)):
            for j in range(tile_length[i]):
                if i % 2 == 0:
                    # this generates which mino is shown
                    initial_stack += random.choice(["80","81","82","83","84","85","86","87"])
                    #initial_stack += possible_minos[mino_pointer % 5]
                    #mino_pointer += 1
                else:
                    # no mino
                    initial_stack += "2F"
        print(initial_stack)
        return initial_stack

    @staticmethod
    def generate_pieces(num_pieces, beginning=None):
        tiles = [
            "00", # L
            "04", # J
            "08", # I
            "0C", # O
            "10", # Z
            "14", # S
            "18"  # T
        ]
        if beginning is None:
            beginning = ''
            pieces_array = []
        else:
            # TODO: make sure it doesn't fail when pieces are rotated
            pieces_array = [int(beginning[i:i + 2], 16) // 4 for i in range(0, len(beginning), 2)]

        for i in range(len(pieces_array), 2):
            pieces_array.append(random.randint(0, 255) % 7)
        three = 0
        for i in range(len(pieces_array), num_pieces):
            for j in range(3):
                new_piece = random.randint(0, 255) % 7
                if pieces_array[i-2] != (pieces_array[i - 2] | pieces_array[i - 1] | new_piece):
                    break
            pieces_array.append(new_piece)
            if pieces_array[i] == 6 and pieces_array[i-2] == pieces_array[i-1] and pieces_array[i-2] == pieces_array[i]:
                three += 1
        random_pieces_as_string = ''.join(list(map(lambda x : tiles[x], pieces_array)))
        return beginning + random_pieces_as_string[len(beginning):]


    async def process(self, client, msg):
        print(f"Processing {client.name} with msg {msg}")
        if msg["type"] == "start":
            # Check if game state is correct.
            if self.state != self.GAME_STATE_LOBBY and self.state != self.GAME_STATE_BETWEEN:
                print("Error: Game already running or finished", self.state)
                return
            # Check if admin.
            if client != self.admin_socket:
                print("Error: Not an admin.")
                return
            print("Starting game!")
            await self.start_game()
        elif msg["type"] == "update":
            if self.state != self.GAME_STATE_RUNNING:
                print("Game is not running. Error.")
                return
            client.height = msg["height"]
            await self.send_gameinfo()
        elif msg["type"] == "lines":
            print("Lines received:", msg["lines"] - 128)
            if self.state != self.GAME_STATE_RUNNING:
                print("Game is not running. Error.")
                return
            await self.send_lines(msg["lines"], client.uuid)
        elif msg["type"] == "reached_30_lines":
            #TODO set num_wins and state
            client.set_winner()
            for c in self.clients:
                if c.uuid == client.uuid:
                    continue
                c.set_dead()
            self.state = self.GAME_STATE_BETWEEN
            await self.send_reached_30_lines(client.uuid)
            await self.send_gameinfo()
        elif msg["type"] == "preset_rng":
            # Check if game state is correct.
            if self.state != self.GAME_STATE_LOBBY:
                print("Error: Game already running or finished")
                return
            # Check if admin.
            if client != self.admin_socket:
                print("Error: Not an admin.")
                return
            print('msg received')
            print(msg)
            if 'garbage' in msg and msg['garbage'] is not None and len(msg["garbage"]) == 200:
                print('received custom garbage')
                self.preset_rng['garbage'] = msg["garbage"]
            else:
                print('bad custom garbage length. must be a string of exactly 200 hex-nibbles')
            if 'pieces' in msg and msg['pieces'] is not None and len(msg['pieces']) > 0 and len(msg['pieces']) % 2 == 0:
                self.preset_rng['pieces'] = msg['pieces'][:512] # preset no more than 256 pieces
            if 'well_column' in msg and msg['well_column'] is not None and len(msg['well_column']) == 2:
                self.preset_rng['well_column'] = msg['well_column']
        elif msg["type"] == "dead":
            if self.state == self.GAME_STATE_FINISHED or self.state == self.GAME_STATE_BETWEEN:
                print("User might just have died.. ignore")
                return
            if self.state != self.GAME_STATE_RUNNING:
                print("Game is not running. Error.")
                return
            print("User died")
            client.set_dead()
            alive_count = self.alive_count()
            if alive_count == 1:
                # We have a winner!
                winner = self.get_last_alive()
                winner.set_winner()
                await winner.send(json.dumps({
                    "type": "win"
                }))
                self.state = self.GAME_STATE_BETWEEN
            await self.send_gameinfo()
        
            

    

class GameHandler:
    def __init__(self):
        pass

sockets = []

games = {}

def parse_register_msg(msg):
    j = json.loads(msg)
    if j["type"] != "register":
        print("Not a registration message")
        return None
    
    return j

async def newserver(websocket, path):
    print("Newserver")
    # First wait for registration message.
    # Without it we don't do anything.
    msg = parse_register_msg(await websocket.recv())
    if msg == None:
        error = {
            "type": "error",
            "msg": "Invalid registration message"
        }
        await websocket.send(json.dumps(error))
        return
    name = msg["name"]

    print(f"New client with name: {name}")
    
    # Next we create a client structure
    client = Client(websocket, name)
    # Send uuid to client
    await client.send(json.dumps({
        "type": "user_info",
        "uuid": client.uuid
    }))

    # Either create a new game
    if(path == "/create"):
        print("Create game")
        new_game = Game(client)
        while new_game.name in games:
            new_game = Game(client)
        client.set_game(new_game)

        print("Sending gameinfo..")
        await new_game.send_gameinfo()
        print("Done")

        games[new_game.name] = new_game

        await client.process()
    # Or join an existing game
    elif(path.startswith("/join/")):
        game_name = path[6:].upper()
        print(f"join game with id: >{game_name}<")
        if not game_name in games:
            error = {
                "type": "error",
                "msg": "Game not found."
            }
            await websocket.send(json.dumps(error))
            return

        game = games[game_name]
        client.set_game(game)

        await game.add_client(client)

        print("Sending gameinfo..")
        await game.send_gameinfo()
        await client.process()

        
    else:
        print(f"Unhandled path: {path}")



async def main():
    async with websockets.serve(newserver, '0.0.0.0', 5678, ping_interval=None):
        await asyncio.get_running_loop().create_future()  # run forever

asyncio.run(main())
