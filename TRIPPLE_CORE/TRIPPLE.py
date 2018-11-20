import pyaudio
import sys
import numpy as np
import aubio

import pygame
import random

from threading import Thread

import math

pygame.init()
pygame.mixer.init()

screen_w = 1200
screen_h = 800
screen_color = (255, 255, 255)
screen = pygame.display.set_mode((screen_w, screen_h))

################################################################################
#                           ANIMATION GRAPHICS CLASS                           #
################################################################################

# speed of particle and ring expansion
expand_speed = 55

# core circle
class Core(object):

	def __init__(self):
		self.xpos = screen_w//2
		self.ypos = screen_h//2
		self.size = 20
		self.color = (0, 0, 0)

	def draw(self):
		pygame.draw.circle(screen, self.color, (self.xpos, self.ypos), self.size)

	def updateSize(self, currIntensity):
		currSize = currIntensity//30
		if currSize > self.size and self.size < 50:
			self.size += 5
		if currSize <= self.size and self.size > 10:
			self.size -= 5 

	def expand(self):
		if self.size < 60:
			self.size += 10
		else:
			self.size = 60

	def updateColor(self, currPitch):
		low_threshold = 500
		high_threshold = 1000

		high = (204, 255, 242)
		mid = (255, 242, 204)
		low = (255, 204, 217)

		if currPitch < low_threshold:
			# low pitch
			self.color = low

		elif currPitch < high_threshold:
			# mid pitch
			self.color = mid

		else:
			# high pitch
			self.color = high

# expanding rings
class Ring(object):

	def __init__(self):
		self.r = expand_speed
		self.color = (240, 240, 240)
		self.width = 1

	def draw(self):
		pygame.draw.circle(screen, self.color, (screen_w//2, screen_h//2),
							self.r, self.width)

	def expand(self):
		self.r += expand_speed

all_sprites = pygame.sprite.Group()

# particle sprite
class Particle(pygame.sprite.Sprite):

	def __init__(self, filename, r, theta):
		pygame.sprite.Sprite.__init__(self)
		file = filename+'.png'
		self.size = 15
		self.image = pygame.image.load(file).convert_alpha()
		self.image = pygame.transform.scale(self.image, (self.size, self.size))
		self.rect = self.image.get_rect()

		self.r = 0
		self.theta = theta
		self.x = screen_w/2 + self.r * math.cos(theta)
		self.y = screen_h/2 + self.r * math.sin(theta)
		self.rect.center = (self.x, self.y)

		all_sprites.add(self)

	def update(self):
		self.r += expand_speed
		self.x = screen_w/2 + self.r * math.cos(self.theta)
		self.y = screen_h/2 + self.r * math.sin(self.theta)
		self.rect.center = (self.x, self.y)
		if self.r > 500:
			all_sprites.remove(self)

	@staticmethod
	def make_new_ring(num, type):
		for i in range(num):
			r = 100
			theta = (360/num) * i
			choose = random.randint(0,4)
			color = 'particles/' + type + str(choose)
			particle = Particle(color, r, theta)

	@staticmethod
	def choose_type(currPitch):
		types = ['warm', 'midwarm', 'midcool', 'cool']
		if currPitch < 200:
			return types[0]
		elif currPitch < 300:
			return types[1]
		elif currPitch < 650:
			return types[2]
		else:
			return types[3]

# clickable buttons
class Button(object):
	def __init__(self, imagefile, ypos):
		self.image = pygame.image.load(imagefile).convert_alpha()
		self.width, self.height = self.image.get_rect().size
		self.xpos = (screen_w / 2) - (self.width / 2)
		self.ypos = ypos
		self._rect = pygame.Rect((self.xpos, self.ypos), (self.width, self.height))

	def changeLoc(self, newX, newY):
		self.xpos = newX
		self.ypos = newY
		self._rect = pygame.Rect((self.xpos, self.ypos), (self.width, self.height))

	def draw(self, screen):
		screen.blit(self.image, self._rect)


################################################################################
#                                 PYAUDIO SET UP                               #
################################################################################

# pyaudio settings
SAMPLERATE = 48000
CHUNK = 1024 * 2
CHANNELS = 1
BUF_SIZE = 1024 * 4
HOP_SIZE = BUF_SIZE//2

# initializae pyaudio
p = pyaudio.PyAudio()

# open stream function
def open_stream(FORMAT):
	return p.open(format = FORMAT,
					channels = CHANNELS,
					rate = SAMPLERATE,
					input = True,
					frames_per_buffer = CHUNK)

# open integer and float streams for analysis
int_Stream = open_stream(pyaudio.paInt16)
flt_Stream = open_stream(pyaudio.paFloat32)


################################################################################
#                       BEAT & PITCH ANALYSIS FUNCTIONS                        #
################################################################################

intensity_list = []
avg_intensity = 0
sensitivity_threshold = 0

"""

beat detection algorithm: 
http://archive.gamedev.net/archive/reference/programming/features/beatdetection/

"""

def get_Intensity():
	while True:
		# retrieve samples
		samples = np.fromstring(int_Stream.read(CHUNK, 
								exception_on_overflow = False), 
								dtype = np.int16)

		# compute the average energy
		intensity = np.average(np.abs(samples))

		global intensity_list, avg_intensity, sensitivity_threshold

		# update the local energy list and keep it to the size of 43
		if len(intensity_list) < 43:
			intensity_list.append(intensity)

		else:
			intensity_list.pop(0)
			intensity_list.append(intensity)

		# compute average local energy
		avg_intensity = sum(intensity_list)/43

		# compute sensitivity threshold 
		sensitivity_threshold = (-0.0025714 * avg_intensity) + 1.5142857

		return int(intensity) 

def get_Pitch():
	# use aubio pitch detector
	while True:
		pitch_detector = aubio.pitch("default", BUF_SIZE, HOP_SIZE, SAMPLERATE)
		pitch_detector.set_unit("Hz")
		pitch_detector.set_silence(-40)
		samples = np.fromstring(flt_Stream.read(CHUNK, 
								exception_on_overflow = False),
								dtype = aubio.float_type)

		currPitch = pitch_detector(samples)[0]

		return currPitch

def is_beat(currIntensity, currPitch):
	# reduce sensitivity by setting minimum intensity and maximum pitch 
	# to be considered a beat
	min_intensity = 300
	max_pitch = 1000
	if currIntensity > sensitivity_threshold * avg_intensity + 500:
		if currIntensity > sensitivity_threshold * avg_intensity + 5000:
			core.expand()
		if currIntensity > min_intensity and currPitch < max_pitch:
			return True
	return False 

################################################################################
#                           FFT ANALYSIS FUNCTIONS                             #
################################################################################

# settings for fft analysis & spectrogram
buckets = 256
bucket_size = int(CHUNK/buckets)
bar_width = 3
bar_margin = (screen_w/buckets)-bar_width

# settings for draw_animation
rings = []	# list of all rings
core = Core() # create core object

def analyze_fft():

	while True:
	# read raw data in bits
		data = int_Stream.read(CHUNK, exception_on_overflow = False)
		# convert into integers
		data_int = np.fromstring(data, dtype = np.int16)
		# convert all data to numpy array
		data_int_array = np.array(data_int)
		# perform fft analysis
		data_fft = np.fft.fft(data_int_array)
		# retrieve real values from fft
		freqs = np.abs(data_fft)

		# list of all max freqs
		all_max_freqs = []
		all_heights = []

		# put into frequency buckets!!!
		for i in range(buckets):

			# put 256 freq points in each bucket
			freqs_in_bucket = freqs[ i * bucket_size : (i+1) * bucket_size ]

			# calculate the largest element in bucket
			max_freq = freqs_in_bucket.max()

			# calculate height using division factor (customizable)
			height = max_freq / 1700
			height = limit_height(height)
			all_heights.append(height)

		return all_heights

def limit_height(height):
	# helper function to limit height of spectrogram
	maxHeight = 300
	if height > maxHeight:
		return 300
	else: return height

def draw_bars(i, screen_w, screen_h, currHeight):
	color = (204, 255, 242)
	pygame.draw.rect(screen, color, 
					(i * (bar_width + bar_margin), 
					screen_h/2 - currHeight/2, 
					bar_width, currHeight))

def draw_fft_spectrum():
	heights = analyze_fft()
	for i in range(buckets):
		draw_bars(i, screen_w, screen_h, heights[i])

################################################################################
#                           DRAW ANIMATION FUNCTIONS                           #
################################################################################

# create buttons

# start_live_btn
liveBtn = Button("logos/START_LIVE_BTN.png", (screen_h * 0.65))

# play_song_btn
playSongBtn = Button("logos/PLAY_SONG_BTN.png", (screen_h * 0.80))

# back_btn
backBtn = Button("logos/BACK_BTN.png", 0)
xpos = 0
ypos = screen_h - backBtn.height
backBtn.changeLoc(xpos, ypos)

# song buttons!!!!!
song_buttons = []
songs = ["Aliens", "ADD", "Square_One"]

for song in songs:
	imagefile = "logos/" + song + ".png"
	songfile = song + ".wav"
	vars()[song + "_BTN"] = Button(imagefile, 
									(screen_h * (0.2 * (songs.index(song)+1))))
	button = vars()[song + "_BTN"]
	song_buttons.append(button)

def draw_animation():
	# BACKGROUND
	screen.fill(screen_color)

	# DRAW SPECTRUM
	draw_fft_spectrum()

	# GET INSTANT ENERGY AND PITCH
	currIntensity = get_Intensity()
	currPitch = get_Pitch()

	# ANIMATION
	# CORE
	core.updateSize(currIntensity)
	core.updateColor(currPitch)

	# RINGS AND PARTICLES
	beat_threshold = 1000
	if is_beat(currIntensity, currPitch):
		# if issa beat, create new ring and particles
		newRing = Ring()
		rings.append(newRing)

		pRing_sizes = [9, 10, 20]
		num = random.choice(pRing_sizes)
		pRing_type = Particle.choose_type(currPitch)
		newParticle = Particle.make_new_ring(num, pRing_type)

	# draw all rings
	for ring in rings:
		ring.draw()
		ring.expand()
		if ring.r >= screen_w:
			rings.remove(ring)

	# draw all particles
	all_sprites.update()
	all_sprites.draw(screen)

	# draw core
	core.draw()

	# back button
	backBtn.draw(screen)

def draw_start_screen():

	screen.fill(screen_color)

	# place title
	logo = pygame.image.load("logos/TITLE.png").convert_alpha()
	logo_w, logo_h = logo.get_rect().size
	logo_xpos = (screen_w / 2) - (logo_w / 2)
	logo_ypos = screen_h * 0.15
	screen.blit(logo, (logo_xpos, logo_ypos))

	# place live spectrum
	draw_fft_spectrum()

	# place live start button
	liveBtn.draw(screen)
	playSongBtn.draw(screen)

def draw_select_screen():

	screen.fill(screen_color)

	for btn in song_buttons:
		btn.draw(screen)

	backBtn.draw(screen)


def run_pygame():

	# start with the start screen
	start_screen = True
	play_screen = False
	select_screen = False
	music_playing = False

	running = True

	while running:
		# quit when closed
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				running = False


		# get mouse click position
		if event.type == pygame.MOUSEBUTTONDOWN:
			xpos, ypos = pygame.mouse.get_pos()

			if liveBtn._rect.collidepoint(xpos, ypos):
				start_screen = False
				play_screen = True

			if playSongBtn._rect.collidepoint(xpos, ypos):
				start_screen = False
				select_screen = True

			if backBtn._rect.collidepoint(xpos, ypos):
				if music_playing:
					pygame.mixer.music.stop()
				start_screen = True
				play_screen = False
				select_screen = False

		if start_screen:
			draw_start_screen()

		if play_screen:
			draw_animation()

		if select_screen:
			draw_select_screen()
			for btn in song_buttons:
				if btn._rect.collidepoint(xpos, ypos):
					songi = song_buttons.index(btn)
					music = "songs/" + songs[songi] + ".wav"
					pygame.mixer.music.load(music)
					pygame.mixer.music.play(0)
					music_playing = True
					select_screen = False
					play_screen = True


		pygame.display.flip()



t1 = Thread(target = get_Intensity)
t2 = Thread(target = get_Pitch)
t3 = Thread(target = analyze_fft)
t1.start()
t2.start()
t3.start()

run_pygame()

int_Stream.stop_stream()
flt_Stream.stop_stream()
int_Stream.close()
flt_Stream.close()
pygame.mixer.quit()
pygame.display.quit()



