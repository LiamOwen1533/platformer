#!/usr/bin/python
"""Platformer"""
# Copyright (C) 2013  Tim Cumming
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Tim Cumming aka Elusive One
# Created: 29/10/13

import os
import pygame
import tmx
from pygame import joystick


def load_sliced_sprites(self, w, h, filename):
    # Master can be any height. Frames must be the same width. Master width will be len(frames)*frame.width
    images = []
    master_image = pygame.image.load(os.path.join('', filename)).convert_alpha()

    # use pygame subsurface for splitting into frames from one image.
    master_width, master_height = master_image.get_size()
    for i in xrange(int(master_width/w)):
        images.append(master_image.subsurface((i*w,0,w,h)))
    return images


class Explosion(pygame.sprite.Sprite):
    def __init__(self, images, location, fps = 10, *groups):
        super(Explosion, self).__init__(*groups)
        self._images = images
        # time this explosion will live for in seconds
        self.lifespan = 0.5

        # Track the time we started, and the time between updates.
        # Then we can figure out when we have to switch the image.
        self._start = pygame.time.get_ticks()
        self._delay = 1000 / fps
        self._last_update = 0
        self._frame = 0

        self.image = self._images[self._frame]
        w, h = self.image.get_size()  # unpack the image size tuple
        
        # location passed from creation is the center of the collided sprite
        # this needs to become the top left of the explosion.
        x, y = location  # unpack the location tuple
        x = x - (w / 2)
        y = y - (h / 2)

        self.rect = pygame.rect.Rect((x, y), (w, h))

    def update(self, dt, game):
        # decrement the lifespan of the explosion by the amount of time passed and
        # remove it from the game if its time runs out
        self.lifespan -= dt
        if self.lifespan < 0:
            self.kill()
            return

        t = pygame.time.get_ticks()

        if t - self._last_update > self._delay:
            self._frame += 1
            if self._frame >= len(self._images): self._frame = 0
            self.image = self._images[self._frame]
            self._last_update = t


class Collectable(pygame.sprite.Sprite):
    def __init__(self, location, *groups):
        super(Collectable, self).__init__(*groups)
        self.image = pygame.image.load('coin.png')
        self.rect = pygame.rect.Rect(location, self.image.get_size())

    def update(self, dt, game):
        if self.rect.colliderect(game.player.rect):
            game.score = game.score + 10
            if game.health < 200:
                game.health = game.health + 5
            self.kill()

#
# Our enemies just move from side to side between "reverse" map triggers.
# They shoot at the player if they are facing them and within 150px.
#
class Enemy(pygame.sprite.Sprite):
    #image = pygame.image.load('enemy.png')
    def __init__(self, location, *groups):
        super(Enemy, self).__init__(*groups)
        self.image = pygame.image.load('enemy-right.png')
        self.right_image = self.image
        self.left_image = pygame.image.load('enemy-left.png')
        self.rect = pygame.rect.Rect(location, self.image.get_size())
        # movement in the X direction; postive is right, negative is left
        self.direction = 1
        # time since the enemy last shot
        self.gun_cooldown = 0

    def update(self, dt, game):
        # move the enemy by 100 pixels per second in the movement direction
        self.rect.x += self.direction * 100 * dt

        # check all reverse triggers in the map to see whether this enemy has
        # touched one
        for cell in game.tilemap.layers['triggers'].collide(self.rect, 'reverse'):
            # reverse movement direction; make sure to move the enemy out of the 
            # collision so it doesn't collide again immediately next update
            if self.direction > 0:
                self.rect.right = cell.left
                self.image = self.left_image
            else:
                self.rect.left = cell.right
                self.image = self.right_image
            self.direction *= -1
            break

        # Check the player rect distance in pixels from the enemy sprite rect.
        if (game.player.rect.y < self.rect.y):
            player_distance = self.rect.y - game.player.rect.y
        else:
            player_distance = game.player.rect.y - self.rect.y

        if (game.player.rect.x < self.rect.x) and not self.gun_cooldown:
            if ((self.rect.x - game.player.rect.x) < 200) and (self.direction == -1) and (player_distance <= 32):
                Bullet('enemy', self.rect.midleft, -1, game.sprites)
                self.gun_cooldown = 1
                game.shoot.play()
        elif not self.gun_cooldown:
            if ((game.player.rect.x - self.rect.x) < 200) and (self.direction == 1) and (player_distance <= 32):
                Bullet('enemy', self.rect.midright, 1, game.sprites)
                self.gun_cooldown = 1
                game.shoot.play()

        # decrement the time since the enemy last shot to a minimum of 0 (so
        # boolean checks work)
        self.gun_cooldown = max(0, self.gun_cooldown - dt)

        # check for collision with the player; on collision mark the flag on the
        # player to indicate game over (a health level could be decremented here
        # instead)
        if self.rect.colliderect(game.player.rect):
            game.health = game.health - 10
            # Lets turn the enemy around if they collide with the player.
            if self.direction > 0:
                self.image = self.left_image
                self.rect.x = self.rect.x - 16
            else:
                self.image = self.right_image
                self.rect.x = self.rect.x + 16
            self.direction *= -1

#
# Bullets fired by the player move in one direction until their lifespan runs
# out or they hit an enemy. This has been extended to allow for enemy bullets.
#
class Bullet(pygame.sprite.Sprite):
    def __init__(self, origin, location, direction, *groups):
        super(Bullet, self).__init__(*groups)
        # lets change the projectile depending on who fired.
        if origin == 'player':
            self.image = pygame.image.load('bullet.png')
        else:
            self.image = pygame.image.load('enemy-bullet.png')
        self.rect = pygame.rect.Rect(location, self.image.get_size())
        # movement in the X direction; postive is right, negative is left;
        # inherited from the origin (player / enemy)
        self.direction = direction
        # time this bullet will live for in seconds
        self.lifespan = 1
        # who fired
        self.origin = origin

    def update(self, dt, game):
        # take a copy of the current position of the player before movement for
        # use in movement collision response        
        last = self.rect.copy()
        # decrement the lifespan of the bullet by the amount of time passed and
        # remove it from the game if its time runs out
        self.lifespan -= dt
        if self.lifespan < 0:
            self.kill()
            return

        # move the bullet by 400 pixels per second in the movement direction
        self.rect.x += self.direction * 400 * dt

        # check for collision with any of the enemy or player sprites; we pass the "kill
        # if collided" flag as True so any collided enemies are removed from the
        # game
        if self.origin == 'player':
            impact = pygame.sprite.spritecollide(self, game.enemies, True)
            if impact:
                Explosion(game.explosion_images, impact[0].rect.center, 10, game.sprites)
                game.explosion.play()
                game.score = game.score + 10
                # we also remove the bullet from the game or it will continue on
                # until its lifespan expires
                self.kill()
        else:
            if self.rect.colliderect(game.player.rect):
                game.explosion.play()
                game.health = game.health - 10
                # game.player.is_dead = True
                # we also remove the bullet from the game or it will continue on
                # until its lifespan expires
                self.kill()

        # Check for wall collisions so we can't fire through.
        new = self.rect
        # look up the tilemap triggers layer for all cells marked "blockers"
        for cell in game.tilemap.layers['triggers'].collide(new, 'blockers'):
            # find the actual value of the blockers property
            blockers = cell['blockers']
            # now for each side set in the blocker check for collision; only
            # collide if we transition through the blocker side 
            # and also check if we originate in the blocker (to avoid
            # false-positives) and remove the bullet from the game
            if 'l' in blockers and new.left <= cell.right:
                game.explosion.play()
                self.kill()
                
            if 'r' in blockers and new.right >= cell.left:
                game.explosion.play()
                self.kill()

            if 'l' in blockers and last.right <= cell.left and new.right > cell.left:
                game.explosion.play()
                self.kill()

            if 'r' in blockers and last.left >= cell.right and new.left < cell.right:
                game.explosion.play()
                self.kill()

# Our player of the game represented as a sprite with many attributes and user
# control.
#
class Player(pygame.sprite.Sprite):
    def __init__(self, location, *groups):
        super(Player, self).__init__(*groups)
        self.image = pygame.image.load('player-right.png')
        self.right_image = self.image
        self.left_image = pygame.image.load('player-left.png')
        self.rect = pygame.rect.Rect(location, self.image.get_size())
        # is the player resting on a surface and able to jump?
        self.resting = False
        # is the player on a ladder?
        self.on_ladder = False
        # is the player touching a wall?
        self.on_wall = False
        # check the previous wall that the player wall jumped from
        self.previous_wall = False
        # player's velocity in the Y axis.
        self.dy = 0
        # player's velocity in the X axis.
        self.dx = 0
        # is the player dead?
        self.is_dead = False
        # movement in the X direction; postive is right, negative is left
        self.direction = 1
        # time since the player last shot
        self.gun_cooldown = 0

    def update(self, dt, game):
        # take a copy of the current position of the player before movement for
        # use in movement collision response
        last = self.rect.copy()

        # handle the player movement left/right keys
        key = pygame.key.get_pressed()
        
        if key[pygame.K_LEFT]:
            self.rect.x -= 300 * dt
            self.image = self.left_image
            self.direction = -1
            self.dx = 0
        if key[pygame.K_RIGHT]:
            self.rect.x += 300 * dt
            self.image = self.right_image
            self.direction = 1
            self.dx = 0
        if key[pygame.K_UP] and self.on_ladder:
            self.rect.y -= 300 * dt
            self.dx = 0
        if key[pygame.K_DOWN] and self.on_ladder:
            self.rect.y += 300 * dt
            self.dx = 0

        # handle the player shooting key
        if (key[pygame.K_LSHIFT]) and not self.gun_cooldown:
            # create a bullet at an appropriate position (the side of the player
            # sprite) and travelling in the correct direction
            if self.direction > 0:
                Bullet('player', self.rect.midright, 1, game.sprites)
            else:
                Bullet('player', self.rect.midleft, -1, game.sprites)
            # set the amount of time until the player can shoot again
            self.gun_cooldown = 0.25
            game.shoot.play()

        # decrement the time since the player last shot to a minimum of 0 (so
        # boolean checks work)
        self.gun_cooldown = max(0, self.gun_cooldown - dt)

        # if the player's allowed to let them jump with the spacebar; note that
        # wall-jumping could be allowed with an additional "touching a wall"
        # flag
        # print(self.previous_wall)  # Debug.

        if (self.resting or self.on_wall) and key[pygame.K_SPACE]:
            game.jump.play()
            # we jump by setting the player's velocity to something large going
            # up (positive Y is down the screen)
            if self.on_wall:
                if self.previous_wall != 'l' and self.on_wall == 'l':
                    self.dy = -500
                    self.dx = 200
                    self.image = self.right_image
                    self.direction = 1
                    self.previous_wall = 'l'
                elif self.previous_wall != 'r' and self.on_wall == 'r':
                    self.dy = -500
                    self.dx = -200
                    self.image = self.left_image
                    self.direction = -1
                    self.previous_wall = 'r'
            else:
                self.dy = -500

        # add gravity on to the currect vertical speed
        if not self.on_ladder:
            self.dy = min(400, self.dy + 40)

        # now add the distance travelled for this update to the player position
        self.rect.y += self.dy * dt
        self.rect.x += self.dx * dt

        # collide the player with the map's blockers
        new = self.rect

        # reset the resting and wall jump triggers; if we are at rest it'll be set again in the
        # loop; this prevents the player from being able to jump if they walk
        # off the edge of a platform
        self.resting = False
        self.on_wall = False
        self.on_ladder = False

        # look up the tilemap triggers layer for all cells marked "action"
        for cell in game.tilemap.layers['triggers'].collide(new, 'action'):
            # find the actual value of the blockers property
            actions = cell['action']
            # now for each side set in the blocker check for collision; only
            # collide if we transition through the blocker side (to avoid
            # false-positives) and align the player with the side collided to
            # make things neater
            if 'l' in actions and new.right <= cell.right and new.left >= cell.left:
                self.on_ladder = True
                self.resting = True
                self.dy = 0
            if 'l' in actions and last.bottom <= cell.top and new.bottom > cell.top:
                self.on_ladder = True
                self.resting = True
                if not key[pygame.K_DOWN]:
                    new.bottom = cell.top
                # reset the vertical speed if we land or hit the roof; this
                # avoids strange additional vertical speed if there's a
                # collision and the player then leaves the ladder
                self.dy = 0
                self.dx = 0    
                self.previous_wall = False

        # look up the tilemap triggers layer for all cells marked "blockers"
        for cell in game.tilemap.layers['triggers'].collide(new, 'blockers'):
            # find the actual value of the blockers property
            blockers = cell['blockers']
            # now for each side set in the blocker check for collision; only
            # collide if we transition through the blocker side (to avoid
            # false-positives) and align the player with the side collided to
            # make things neater
            if 'l' in blockers and last.right <= cell.left and new.right > cell.left:
                new.right = cell.left
                self.on_wall = 'r'
            if 'r' in blockers and last.left >= cell.right and new.left < cell.right:
                new.left = cell.right
                self.on_wall = 'l'
            if 't' in blockers and last.bottom <= cell.top and new.bottom > cell.top:
                self.resting = True
                new.bottom = cell.top
                # reset the vertical speed if we land or hit the roof; this
                # avoids strange additional vertical speed if there's a
                # collision and the player then leaves the platform
                self.dy = 0
                self.dx = 0    
                self.previous_wall = False
            if 'b' in blockers and last.top >= cell.bottom and new.top < cell.bottom:
                new.top = cell.bottom
                self.dy = 0
                self.dx = 0

        # re-focus the tilemap viewport on the player's new position
        game.tilemap.set_focus(new.x, new.y)

#
# Our game class represents one loaded level of the game and stores all the
# actors and other game-level state.
#
class Game(object):
    def main(self, screen):
        # grab a clock so we can limit and measure the passing of time
        clock = pygame.time.Clock()

        # Lets keep score
        self.score = 0
        # Player health
        self.health = 200
        # Player Lives
        self.lives = 3

        # we draw the background as a static image so we can just load it in the
        # main loop
        background = pygame.image.load('background.png')

        # load our tilemap and set the viewport for rendering to the screen's
        # size
        self.tilemap = tmx.load('new-map.tmx', screen.get_size())

        # add a layer for our sprites controlled by the tilemap scrolling
        self.sprites = tmx.SpriteLayer()
        self.tilemap.layers.append(self.sprites)
        # fine the player start cell in the triggers layer
        start_cell = self.tilemap.layers['triggers'].find('player')[0]
        # use the "pixel" x and y coordinates for the player start
        self.player = Player((start_cell.px, start_cell.py), self.sprites)

        # add a separate layer for enemies so we can find them more easily later
        self.enemies = tmx.SpriteLayer()
        self.tilemap.layers.append(self.enemies)
        # add an enemy for each "enemy" trigger in the map
        for enemy in self.tilemap.layers['triggers'].find('enemy'):
            Enemy((enemy.px, enemy.py), self.enemies)

        # add a separate layer for coins so we can find them more easily later
        self.coins = tmx.SpriteLayer()
        self.tilemap.layers.append(self.coins)
        # add an coin for each "coin" trigger in the map
        for coin in self.tilemap.layers['triggers'].find('coin'):
            Collectable((coin.px, coin.py), self.coins)

        self.explosion_images = load_sliced_sprites(0, 20, 20, 'explosion-sprite.png')

        # load the sound effects used in playing a level of the game
        self.jump = pygame.mixer.Sound('jump.wav')
        self.shoot = pygame.mixer.Sound('shoot.wav')
        self.explosion = pygame.mixer.Sound('explosion.wav')

        while 1:
            # limit updates to 30 times per second and determine how much time
            # passed since the last update
            dt = clock.tick(25)

            # handle basic game events; terminate this main loop if the window
            # is closed or the escape key is pressed
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return

            # update the tilemap and everything in it passing the elapsed time
            # since the last update (in seconds) and this Game object
            self.tilemap.update(dt / 1000., self)
            # construct the scene by drawing the background and then the rest of
            # the game imagery over the top
            screen.blit(background, (0, 0))
            self.tilemap.draw(screen)

            basicFont = pygame.font.Font('freesansbold.ttf', 18)
            textColor = (255, 255, 255)

            scoreSurf = basicFont.render('Score: %s' % (self.score), 1, textColor)
            scoreRect = scoreSurf.get_rect()
            scoreRect.topleft = (20, 50)
            screen.blit(scoreSurf, scoreRect)
            
            healthSurf = basicFont.render('Health: ', 1, textColor)
            healthRect = healthSurf.get_rect()
            healthRect.topleft = (20, 10)
            screen.blit(healthSurf, healthRect)

            healthbar = pygame.image.load("healthbar.png")
            health = pygame.image.load("health.png")

            screen.blit(healthbar, (90,11))
            for health1 in range(self.health):
                screen.blit(health, (health1+93,14))

            livesSurf = basicFont.render('Lives: %s' % (self.lives), 1, textColor)
            livesRect = livesSurf.get_rect()
            livesRect.topleft = (20, 30)
            screen.blit (livesSurf, livesRect)
            
            pygame.display.update()

            # terminate this main loop if the player dies; a simple change here
            # could be to replace the "print" with the invocation of a simple
            # "game over" scene
            #if self.player.is_dead:
            if self.health <= 0:
                self.lives = self.lives - 1
                self.health = 200
                self.explosion.play()
                self.player.rect = pygame.rect.Rect((start_cell.px, start_cell.py), self.player.image.get_size())

            gameover = pygame.image.load("gameover.png")
            youwin = pygame.image.load("youwin.png")

            if self.lives == 0:
                screen.blit(gameover, (0,0))
                pygame.display.update()
                return

            if self.tilemap.layers['triggers'].collide(self.player.rect, 'exit'):
                screen.blit(youwin, (0,0))
                pygame.display.update()
                return

if __name__ == '__main__':
    # if we're invoked as a program then initialise pygame, create a window and
    # run the game
    pygame.init()
    screen = pygame.display.set_mode((640, 360))
    Game().main(screen)

