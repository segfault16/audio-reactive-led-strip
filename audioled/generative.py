from __future__ import (absolute_import, division, print_function, unicode_literals)

import math
import random
from collections import OrderedDict
import os.path

import numpy as np
import scipy as sp
from scipy import signal as signal

from audioled.effect import Effect

from PIL import Image, ImageOps

import logging
logger = logging.getLogger(__name__)

wave_modes = ['sin', 'sawtooth', 'sawtooth_reversed', 'square']
wave_mode_default = 'sin'
sortby = ['red', 'green', 'blue', 'brightness']
sortbydefault = 'red'
direction = ['side1', 'side2', 'random']
direction_default = 'random'
waveshape = ['sin(x)', '1/x', '1/x**2', '1/x**3', 'const(x)', 'x', 'x**2', 'x**3', 'x * e**(-x)',
             '-sin(x)', '-1/x', '-1/x**2', '-1/x**3', '-const(x)', '-x', '-x**2', '-x**3', '-x * e**(-x)',
             'all positive', 'all negative', 'all']
waveshape_pos = ['sin(x)', '1/x', '1/x**2', '1/x**3', 'const(x)', 'x', 'x**2', 'x**3', 'x * e**(-x)']
waveshape_neg = ['-sin(x)', '-1/x', '-1/x**2', '-1/x**3', '-const(x)', '-x', '-x**2', '-x**3', '-x * e**(-x)']
waveshape_default = 'sin(x)'


class SwimmingPool(Effect):
    """Generates a wave effect to look like the reflection on the bottom of a swimming pool."""

    @staticmethod
    def getEffectDescription():
        return \
            """
            Generates a wave effect to look like the reflection on the bottom of a swimming pool.
            """

    def __init__(self,
                 num_waves=30,
                 scale=0.2,
                 wavespread_low=30,
                 wavespread_high=70,
                 max_speed=30,
                 min_speed=10,
                 direction=direction_default,
                 waveshape=waveshape_default):
        self.num_waves = num_waves
        self.scale = scale
        self.wavespread_low = wavespread_low
        self.wavespread_high = wavespread_high
        self.max_speed = max_speed
        self.min_speed = min_speed
        self.direction = direction
        self.waveshape = waveshape
        self.__initstate__()

    def __initstate__(self):
        # state
        try:
            self.direction
        except AttributeError:
            self.direction = direction_default
        try:
            self.waveshape
        except AttributeError:
            self.waveshape = waveshape_default
        try:
            self._pixel_state
        except AttributeError:
            self._pixel_state = None
        try:
            self._last_t
        except AttributeError:
            self._last_t = 0.0
        try:
            self._Wave
        except AttributeError:
            self._Wave = None
        try:
            self._WaveSpecSpeed
        except AttributeError:
            self._WaveSpecSpeed = None
        try:
            self._rotate_counter
        except AttributeError:
            self._rotate_counter = 0
        super(SwimmingPool, self).__initstate__()

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters":
            OrderedDict([
                # default, min, max, stepsize
                ("num_waves", [30, 1, 100, 1]),
                ("scale", [0.2, 0.01, 1.0, 0.01]),
                ("wavespread_low", [30, 1, 100, 1]),
                ("wavespread_high", [70, 2, 150, 1]),
                ("max_speed", [30, 1, 200, 1]),
                ("min_speed", [30, 1, 200, 1]),
                ("direction", direction),
                ("waveshape", waveshape),
            ])
        }
        return definition

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "num_waves": "Number of generated overlaying waves.",
                "scale": "Scales the brightness of the waves.",
                "wavespread_low": "Minimal spread of the randomly generated waves.",
                "wavespread_high": "Maximum spread of the randomly generated waves.",
                "max_speed": "Maximum movement speed of the waves.",
                "min_speed": "Minimum movement speed of the waves.",
                "direction": "Select a direction or random behavior.",
                "waveshape": "Select type of waves to spawn."
            }
        }
        return help

    def getParameter(self):
        definition = self.getParameterDefinition()
        definition['parameters']['num_waves'][0] = self.num_waves
        definition['parameters']['scale'][0] = self.scale
        definition['parameters']['wavespread_low'][0] = self.wavespread_low
        definition['parameters']['wavespread_high'][0] = self.wavespread_high
        definition['parameters']['max_speed'][0] = self.max_speed
        definition['parameters']['min_speed'][0] = self.min_speed
        definition['parameters']['direction'] = [self.direction] + [x for x in direction if x != self.direction]
        definition['parameters']['waveshape'] = [self.waveshape] + [x for x in waveshape if x != self.waveshape]
        return definition

    def _createWaveform(self, spread, wave_hight, speed, wave_form):
        # Added negatives. Flip will happen later. This is just to get the form.
        # Symmetricals are for integrity and for selection in all negatives.
        if wave_form == 'sin(x)' or wave_form == '-sin(x)':
            return np.asarray(sp.ndimage.gaussian_filter([0, 0] + [math.sin(math.pi / spread * i) * wave_hight for i in range(1, spread + 1)] + [0, 0], sigma=3))
        elif wave_form == '1/x' or wave_form == '-1/x':
            return np.asarray(sp.ndimage.gaussian_filter([0, 0] + [spread / 2 / i * wave_hight for i in range(1, spread + 1)] + [0, 0], sigma=3))
        elif wave_form == '1/x**2' or wave_form == '-1/x**2':
            return np.asarray(sp.ndimage.gaussian_filter([0, 0] + [spread / 2 / i**2 * wave_hight for i in range(1, spread + 1)] + [0, 0], sigma=3))
        elif wave_form == '1/x**3' or wave_form == '-1/x**3':
            return np.asarray(sp.ndimage.gaussian_filter([0, 0] + [spread / 2 / i**3 * wave_hight for i in range(1, spread + 1)] + [0, 0], sigma=3))
        elif wave_form == 'const(x)' or wave_form == '-const(x)':
            return np.asarray(sp.ndimage.gaussian_filter([0, 0] + [wave_hight for i in range(1, spread + 1)] + [0, 0], sigma=3))
        elif wave_form == 'x' or wave_form == '-x':
            return np.asarray(sp.ndimage.gaussian_filter([0, 0] + [i * wave_hight / spread for i in range(1, spread + 1)] + [0, 0], sigma=3))
        elif wave_form == 'x**2' or wave_form == '-x**2':
            return np.asarray(sp.ndimage.gaussian_filter([0, 0] + [i**2 * wave_hight / spread / 10 for i in range(1, spread + 1)] + [0, 0], sigma=3))
        elif wave_form == 'x**3' or wave_form == '-x**3':
            return np.asarray(sp.ndimage.gaussian_filter([0, 0] + [i**3 * wave_hight / spread / 100 for i in range(1, spread + 1)] + [0, 0], sigma=3))
        elif wave_form == 'x * e**(-x)' or wave_form == '-x * e**(-x)':
            return np.asarray(sp.ndimage.gaussian_filter([0, 0] + [(0.5 / spread) * i * math.exp(-(0.2 / spread) * i) * wave_hight for i in range(1, spread + 1)] + [0, 0], sigma=3))
        # Default
        return np.asarray(sp.ndimage.gaussian_filter([0, 0] + [math.sin(math.pi / spread * i) * wave_hight for i in range(1, spread + 1)] + [0, 0], sigma=3))

    def _createWave(self, _spread, _wavehight, _speed):
        # Create array for a single wave
        _CArray = np.empty(0)
        _spread = min(int(self._num_pixels / 2) - 1, _spread)

        # Select the type of waves
        if self.waveshape == 'all':
            wave_selector = random.choice(waveshape[:-3])
        elif self.waveshape == 'all positive':
            wave_selector = random.choice(waveshape_pos)
        elif self.waveshape == 'all negative':
            wave_selector = random.choice(waveshape_neg)
        else:
            wave_selector = self.waveshape
        _CArray = self._createWaveform(_spread, _wavehight, _speed, wave_selector)
        if wave_selector.startswith('-'):
            _CArray = np.flip(_CArray)
        _output = np.zeros(self._num_pixels)
        _output[:len(_CArray)] = _CArray
        # Move somewhere
        _output = np.roll(_output, np.random.randint(0, self._num_pixels), axis=0)
        return _output.clip(0.0, 255.0)

    def _initWaves(self, num_waves, wavespread_low=50, wavespread_high=100, max_speed=30):
        wavespread_low = int(wavespread_low)
        wavespread_high = int(wavespread_high)
        num_waves = int(num_waves)
        max_speed = int(max_speed)
        _WaveArray = []
        _wavespread = np.random.randint(wavespread_low, wavespread_high, num_waves)
        _WaveArraySpecSpeed = np.random.randint(-max_speed, max_speed, num_waves)
        _WaveArraySpecHeight = np.random.rand(num_waves)
        for i in range(0, num_waves):
            _WaveArray.append(self._createWave(_wavespread[i], _WaveArraySpecHeight[i], _WaveArraySpecSpeed[i]))
        return _WaveArray, _WaveArraySpecSpeed

    def numInputChannels(self):
        return 1

    def numOutputChannels(self):
        return 1

    async def update(self, dt):
        await super().update(dt)
        if self._num_pixels is None:
            return
        if self._pixel_state is None or np.size(self._pixel_state, 1) != self._num_pixels:
            self._pixel_state = np.zeros(self._num_pixels) * np.array([[0.0], [0.0], [0.0]])
            self._Wave = None
            self._WaveSpecSpeed = None

        if self._Wave is None or self._WaveSpecSpeed is None or len(self._Wave) < int(self.num_waves):
            self._Wave, self._WaveSpecSpeed = self._initWaves(
                self.num_waves,
                self.wavespread_low,
                self.wavespread_high,
                self.max_speed)
        # Rotate waves
        self._rotate_counter += 1
        if self._rotate_counter > 30:
            self._Wave = np.roll(self._Wave, 1, axis=0)
            self._WaveSpecSpeed = np.roll(self._WaveSpecSpeed, 1)
            if self.max_speed > self.min_speed:
                speed = np.random.randint(self.min_speed, self.max_speed)
            else:
                speed = np.random.randint(0, self.max_speed)
            if self.direction == 'side1':
                speed = speed * -1
            elif self.direction == 'random':
                speed = speed * random.choice([-1, 1])
            spread = np.random.randint(self.wavespread_low, self.wavespread_high)
            height = np.random.rand()
            wave = self._createWave(spread, height, speed)
            self._Wave[0] = wave
            self._WaveSpecSpeed[0] = speed
            self._rotate_counter = 0

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        if not self._inputBufferValid(0):
            color = np.ones(self._num_pixels) * np.array([[255], [255], [255]])
        else:
            color = self._inputBuffer[0]

        all_waves = np.zeros(self._num_pixels)
        for i in range(0, int(self.num_waves)):
            fact = 1.0
            if i == 0:
                fact = (self._rotate_counter / 30)
            if i == self.num_waves - 1:
                fact = (1.0 - self._rotate_counter / 30)
            if i < len(self._Wave) and i < len(self._WaveSpecSpeed):
                
                step = sp.ndimage.interpolation.shift(
                    self._Wave[i],
                    self._t * self._WaveSpecSpeed[i],
                    mode='wrap',
                    prefilter=True) * self.scale * fact
                # step = np.roll(self._Wave[i], int(self._t * self._WaveSpecSpeed[i]), axis=0) * self.scale * fact
                all_waves += step

        self._outputBuffer[0] = np.multiply(color, all_waves).clip(0, 255.0)


class DefenceMode(Effect):
    """Generates a colorchanging strobe light effect.
    The mode to defend against all kinds of attackers.
    """
    @staticmethod
    def getEffectDescription():
        return \
            "Generates a color-changing strobe light effect."

    def __init__(self, scale=0.2):
        self.scale = scale
        self.__initstate__()

    def __initstate__(self):
        # state
        super(DefenceMode, self).__initstate__()

    def numInputChannels(self):
        return 1

    def numOutputChannels(self):
        return 1

    def process(self):
        if self._outputBuffer is not None:
            # color = self._inputBuffer[0]
            A = random.choice([True, False, False])
            if A is True:
                self._output = np.ones(self._num_pixels) * np.array([[random.randint(
                    0.0, 255.0)], [random.randint(0.0, 255.0)], [random.randint(0.0, 255.0)]])
            else:
                self._output = np.zeros(self._num_pixels) * np.array([[0.0], [0.0], [0.0]])

            self._outputBuffer[0] = self._output.clip(0.0, 255.0)


class MidiKeyboard(Effect):
    """Effect for handling midi inputs."""
    @staticmethod
    def getEffectDescription():
        return \
            "Effect for handling midi inputs."

    class Note(object):
        def __init__(self, note, velocity, spawn_time):
            self.note = note
            self.velocity = velocity
            self.spawn_time = spawn_time
            self.active = True
            self.value = 0.0
            self.release_time = 0.0

    def __init__(self, midiPort='', attack=0.0, decay=0.0, sustain=1.0, release=0.0):

        self.midiPort = midiPort
        self.attack = attack
        self.decay = decay
        self.sustain = sustain
        self.release = release
        self.__initstate__()

    def __initstate__(self):
        super(MidiKeyboard, self).__initstate__()
        try:
            import mido
        except ImportError as e:
            logger.error('Unable to import the mido library')
            logger.error('You can install this library with `pip install mido`')
            raise e
        try:
            self._midi.close()
        except Exception:
            pass
        try:
            self._midi = mido.open_input(self.midiPort)
        except OSError as e:
            self._midi = mido.open_input()
            self.midiPort = self._midi.name
            logger.info("Not connected midi device {}".format(self.midiPort))
            logger.error(e)
        self._on_notes = []

    def numInputChannels(self):
        return 1  # color

    def numOutputChannels(self):
        return 1

    @staticmethod
    def getMidiPorts():
        try:
            import mido
            return mido.get_input_names()
        except ImportError:
            logger.error('Unable to import the mido library')
            logger.error('You can install this library with `pip install mido`')
            return []
        except Exception:
            logger.error("Error while getting midi inputs")
            return []

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters": {
                # default, min, max, stepsize
                "midiPort": MidiKeyboard.getMidiPorts(),
                "attack": [0.0, 0.0, 5.0, 0.01],
                "decay": [0.0, 0.0, 5.0, 0.01],
                "sustain": [1.0, 0.0, 1.0, 0.01],
                "release": [0.0, 0.0, 5.0, 0.01],
            }
        }
        return definition

    def getModulateableParameters(self):
        params = super().getModulateableParameters()
        params.remove('midiPort')
        return params

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "midiPort": "Midi Port to use.",
                "attack": "Controls attack in pixel envelope.",
                "decay": "Controls decay in pixel envelope.",
                "sustain": "Controls sustain in pixel envelope.",
                "release": "Controls release in pixel envelope.",
            }
        }
        return help

    def getParameter(self):
        definition = super().getParameter()
        definition['parameters']['midiPort'] = [self.midiPort
                                                ] + [x for x in MidiKeyboard.getMidiPorts() if x != self.midiPort]
        return definition

    async def update(self, dt):
        await super().update(dt)
        # Process midi notes
        for msg in self._midi.iter_pending():
            if msg.type == 'note_on':
                self._on_notes.append(MidiKeyboard.Note(msg.note, msg.velocity, self._t))
            if msg.type == 'note_off':
                toRemove = [note for note in self._on_notes if note.note == msg.note]
                for note in toRemove:
                    note.active = False
                    note.release_time = self._t

        # Process note states
        for note in self._on_notes:
            if note.active:

                if self._t - note.spawn_time < self.attack:
                    # attack phase
                    note.value = note.velocity * (self._t - note.spawn_time) / self.attack
                elif self._t - note.spawn_time < self.attack + self.decay:
                    # decay phase
                    # time since attack phase ended: self._t - note.spawn_time - self.attack
                    decay_fact = 1.0 - (self._t - note.spawn_time - self.attack) / self.decay
                    # linear interpolation
                    # decay_fact = 0.0: decay beginning -> 1.0
                    # decay_fact = 1.0: decay ending -> sustain
                    note.value = note.velocity * (self.sustain + (1.0 - self.sustain) * decay_fact)
                else:
                    # sustain phase
                    note.value = note.velocity * self.sustain
            else:
                # release phase
                if self._t - note.release_time < self.release:
                    note.value = note.velocity * (1.0 - (self._t - note.release_time) / self.release) * self.sustain
                else:
                    self._on_notes.remove(note)

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        if not self._inputBufferValid(0):
            col = np.ones(self._num_pixels) * np.array([[255], [255], [255]])
        else:
            col = self._inputBuffer[0]

        # Draw
        pos = np.zeros(self._num_pixels)
        for note in self._on_notes:
            index = int(max(0, min(self._num_pixels - 1, float(note.note) / 127.0 * self._num_pixels)))
            pos[index] = 1 * note.value / 127.0
        self._outputBuffer[0] = np.multiply(pos, col)


class Breathing(Effect):
    """Effect for simulating breathing behavior over brightness."""
    @staticmethod
    def getEffectDescription():
        return \
            "Effect for simulating breathing behavior over brightness."

    def __init__(self, cycle=5):
        self.cycle = cycle
        self.__initstate__()

    def __initstate__(self):
        # state
        super(Breathing, self).__initstate__()

    def numInputChannels(self):
        return 1

    def numOutputChannels(self):
        return 1

    def oneStar(self, t, cycle):
        brightness = 0.5 * math.sin((2 * math.pi) / cycle * t) + 0.5
        return brightness

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters": OrderedDict([
                # default, min, max, stepsize
                ("cycle", [5, 0.1, 10, 0.1]),
            ])
        }
        return definition

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "cycle": "Seconds to repeat a full cycle.",
            }
        }
        return help

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        color = self._inputBuffer[0]
        if color is None:
            color = np.ones(self._num_pixels) * np.array([[255.0], [255.0], [255.0]])
        if self._outputBuffer is not None:
            brightness = self.oneStar(self._t, self.cycle)
            self._output = np.multiply(color, np.ones(self._num_pixels) * np.array([[brightness], [brightness], [brightness]]))
        self._outputBuffer[0] = self._output.clip(0.0, 255.0)


class Heartbeat(Effect):
    """Effect for simulating a beating heart over brightness."""
    @staticmethod
    def getEffectDescription():
        return \
            "Effect for simulating a beating heart over brightness."

    def __init__(self, speed=1):
        self.speed = speed
        self.__initstate__()

    def __initstate__(self):
        # state
        super(Heartbeat, self).__initstate__()

    def numInputChannels(self):
        return 1

    def numOutputChannels(self):
        return 1

    def oneStar(self, t, speed):
        brightness = abs(math.sin(speed * t)**63 * math.sin(speed * t + 1.5) * 8)
        return brightness

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters": OrderedDict([
                # default, min, max, stepsize
                ("speed", [1, 0.1, 100, 0.1]),
            ])
        }
        return definition

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "speed": "Speed of the heartbeat.",
            }
        }
        return help

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        if not self._inputBufferValid(0):
            color = np.ones(self._num_pixels) * np.array([[255.0], [0.0], [0.0]])
        else:
            color = self._inputBuffer[0]

        brightness = self.oneStar(self._t, self.speed)
        self._output = np.multiply(color, np.ones(self._num_pixels) * np.array([[brightness], [brightness], [brightness]]))
        self._outputBuffer[0] = self._output.clip(0.0, 255.0)


class FallingStars(Effect):
    """Effect for creating random stars that fade over time."""
    @staticmethod
    def getEffectDescription():
        return \
            "Effect for creating random stars that fade over time."

    def __init__(self, dim_speed=100, thickness=1, spawntime=0.1, max_brightness=1, probability=0.1, max_spawns=1):
        self.dim_speed = dim_speed
        self.thickness = thickness
        self.max_brightness = max_brightness
        self.probability = probability
        self.max_spawns = max_spawns
        self.__initstate__()

    def __initstate__(self):
        # state
        self._t0Array = []
        self._spawnArray = []
        self._starCounter = 0
        self._spawnflag = True
        self._lastSpawn = 0
        super(FallingStars, self).__initstate__()

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters":
            OrderedDict([
                # default, min, max, stepsize
                ("dim_speed", [100, 1, 1000, 1]),
                ("thickness", [1, 1, 300, 1]),
                ("probability", [0.1, 0.0, 1.0, 0.01]),
                ("max_spawns", [10, 1, 10, 1]),
                ("max_brightness", [1, 0, 1, 0.01]),
            ])
        }
        return definition

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "dim_speed": "Time to fade out one star.",
                "thickness": "Thickness of one star in pixels.",
                "max_brightness": "Maximum brightness of the stars.",
                "probability": "Probability of spawning a new star even if there's no audio peak.",
                "max_spawns": "Maximum number of spawning stars per frame."
            }
        }
        return help

    def numInputChannels(self):
        return 1

    def numOutputChannels(self):
        return 1

    def spawnStar(self):
        self._starCounter += 1
        self._t0Array.append(self._t)
        self._spawnArray.append(random.randint(0, self._num_pixels - self.thickness))
        if self._starCounter > 100:
            self._starCounter -= 1
            self._t0Array.pop(0)
            self._spawnArray.pop(0)

    def allStars(self, t, dim_speed, thickness, t0, spawnSpot):
        controlArray = []
        for i in range(0, self._starCounter):
            oneStarArray = np.zeros(self._num_pixels)
            for j in range(0, thickness):
                if i < len(spawnSpot):
                    index = spawnSpot[i] + j
                    if index < self._num_pixels:
                        oneStarArray[index] = math.exp(-(100 / dim_speed) * (self._t - t0[i]))
            controlArray.append(oneStarArray)
        return controlArray

    def starControl(self, prob):
        for _ in range(int(self.max_spawns)):
            if random.random() <= prob:
                self.spawnStar()
        outputArray = self.allStars(self._t, self.dim_speed, self.thickness, self._t0Array, self._spawnArray)
        return np.sum(outputArray, axis=0)

    async def update(self, dt):
        await super().update(dt)

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        color = self._inputBuffer[0]
        if color is None:
            color = np.ones(self._num_pixels) * np.array([[255.0], [255.0], [255.0]])
        if self._outputBuffer is not None:

            self._output = np.multiply(
                color,
                self.starControl(self.probability)
                * np.array([[self.max_brightness * 1.0], [self.max_brightness * 1.0], [self.max_brightness * 1.0]]))

        self._outputBuffer[0] = self._output.clip(0.0, 255.0)


class Pendulum(Effect):
    """Generates a blob of light to swing back and forth."""
    @staticmethod
    def getEffectDescription():
        return \
            "Generates a blob of light to swing back and forth."

    def __init__(self, spread=0.03, location=0.5, displacement=0.15, heightactivator=True, lightflip=True, swingspeed=1):

        self.spread = spread
        self.location = location
        self.displacement = displacement
        self.heightactivator = heightactivator
        self.lightflip = lightflip
        self.swingspeed = swingspeed
        self.__initstate__()

    def __initstate__(self):
        # state
        super(Pendulum, self).__initstate__()

    def __setstate__(self, state):
        if 'spread' in state and state['spread'] > 1:
            state['spread'] = state['spread'] / 300
        if 'location' in state and state['location'] > 1:
            state['location'] = state['location'] / 300
        if 'displacement' in state and state['displacement'] > 3:
            state['displacement'] = state['displacement'] / 300
        return super().__setstate__(state)

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters":
            OrderedDict([
                # default, min, max, stepsize
                ("location", [0, 0, 1, 0.01]),
                ("displacement", [0.15, 0, 3, 0.01]),
                ("swingspeed", [1, 0, 5, 0.01]),
                ("heightactivator", False),
                ("lightflip", False),
            ])
        }
        return definition

    def getModulateableParameters(self):
        params = super().getModulateableParameters()
        params.remove('heightactivator')
        params.remove('lightflip')
        return params

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "location": "Starting location and center to swing around.",
                "displacement": "Displacement of the pendulum to either side.",
                "swingspeed": "Speed of the pendulum.",
                "heightactivator": "Changes brightness of the pendulum depending on its location.",
                "lightflip": "Reverses the setting of heightactivator."
            }
        }
        return help

    def createBlob(self, spread_rel, location_rel):
        blobArray = np.zeros(self._num_pixels)
        spread = max(int(spread_rel * self._num_pixels), 1)
        location = int(location_rel * self._num_pixels)
        for i in range(-spread, spread + 1):
            if (location + i) >= 0 and (location + i) < self._num_pixels:
                blobArray[location + i] = math.cos((math.pi / spread) * i)
        return blobArray.clip(0.0, 255.0)

    def moveBlob(self, blobArray, displacement_rel, swingspeed):
        displacement = displacement_rel * self._num_pixels
        outputArray = sp.ndimage.interpolation.shift(blobArray,
                                                     displacement * math.sin(self._t * swingspeed),
                                                     mode='wrap',
                                                     prefilter=True)
        return outputArray

    def controlBlobs(self):
        output = self.moveBlob(self.createBlob(self.spread, self.location), self.displacement, self.swingspeed)
        return output

    def numInputChannels(self):
        return 1

    def numOutputChannels(self):
        return 1

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        if self._inputBufferValid(0):
            color = self._inputBuffer[0]
        else:
            # default: all white
            color = np.ones(self._num_pixels) * np.array([[255.0], [255.0], [255.0]])
        if self.heightactivator is True:
            if self.lightflip is True:
                lightconfig = -1.0
            else:
                lightconfig = 1.0
            configArray = lightconfig * math.cos(2 * self._t) * np.array([[1.0], [1.0], [1.0]])
        else:
            configArray = np.array([[1.0], [1.0], [1.0]])
        self._output = np.multiply(color, self.controlBlobs() * configArray)
        self._outputBuffer[0] = self._output.clip(0.0, 255.0)


class RandomPendulums(Effect):
    """Randomly generates a number of pendulums."""
    @staticmethod
    def getEffectDescription():
        return \
            "Randomly generates a number of pendulums."

    def __init__(self, num_pendulums=100, dim=0.1):
        self.num_pendulums = num_pendulums
        self.dim = dim
        self.__initstate__()

    def __initstate__(self):
        super(RandomPendulums, self).__initstate__()
        # state
        self._spread = []
        self._location = []
        self._displacement = []
        self._heightactivator = []
        self._lightflip = []
        self._offset = []
        self._swingspeed = []

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters":
            OrderedDict([
                # default, min, max, stepsize
                ("num_pendulums", [20, 1, 300, 1]),
                ("dim", [1, 0, 1, 0.01]),
            ])
        }
        return definition

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "num_pendulums": "Number of random pendulums.",
                "dim": "Overall brightness of the pendulums.",
            }
        }
        return help

    def createBlob(self, spread_rel, location_rel):
        blobArray = np.zeros(self._num_pixels)
        spread = max(int(spread_rel * self._num_pixels), 1)
        location = int(location_rel * self._num_pixels)
        for i in range(-spread, spread + 1):
            if (location + i) >= 0 and (location + i) < self._num_pixels:
                blobArray[location + i] = math.cos((math.pi / spread) * i)
        return blobArray.clip(0.0, 255.0)

    def moveBlob(self, blobArray, displacement_rel, offset_rel, swingspeed):
        config = displacement_rel * self._num_pixels * math.sin((self._t * swingspeed) + offset_rel * self._num_pixels)
        outputArray = sp.ndimage.interpolation.shift(blobArray, config, mode='wrap', prefilter=True)
        return outputArray.clip(0.0, 255.0)

    def controlBlobs(self, spread_rel, location_rel, displacement_rel, offset_rel, swingspeed):
        output = self.moveBlob(self.createBlob(spread_rel, location_rel), displacement_rel, offset_rel, swingspeed)
        return output

    def numInputChannels(self):
        return 1

    def numOutputChannels(self):
        return 1

    async def update(self, dt):
        await super().update(dt)
        if self._num_pixels is None:
            return
        if len(self._spread) == 0 or len(self._spread) != self.num_pendulums:
            self._spread = []
            self._location = []
            self._displacement = []
            self._heightactivator = []
            self._lightflip = []
            self._offset = []
            self._swingspeed = []
            for _ in range(self.num_pendulums):
                rSpread = int(random.randint(2, 10) / 300 * self._num_pixels)
                self._spread.append(rSpread / 300)
                self._location.append(random.randint(0, self._num_pixels - rSpread - 1) / 300)
                self._displacement.append(random.randint(5, 50) / 300)
                self._heightactivator.append(random.choice([True, False]))
                self._lightflip.append(random.choice([True, False]))
                self._offset.append(random.uniform(0, 6.5) / 300)
                self._swingspeed.append(random.uniform(0, 1))

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        if self._inputBufferValid(0):
            color = self._inputBuffer[0]
        else:
            # default: all white
            color = np.ones(self._num_pixels) * np.array([[255.0], [255.0], [255.0]])

        self._output = np.zeros(self._num_pixels) * np.array([[0.0], [0.0], [0.0]])
        for i in range(self.num_pendulums):
            if self._heightactivator[i] is True:
                if self._lightflip[i] is True:
                    lightconfig = -1.0
                else:
                    lightconfig = 1.0
                configArray = lightconfig * self.dim * math.cos(2 * self._t + self._offset[i]) * np.array([[1.0], [1.0], [1.0]
                                                                                                           ])
            else:
                configArray = np.array([[1.0 * self.dim], [1.0 * self.dim], [1.0 * self.dim]])
            self._output += np.multiply(
                color,
                self.controlBlobs(self._spread[i], self._location[i], self._displacement[i], self._offset[i],
                                  self._swingspeed[i]) * configArray)
        self._outputBuffer[0] = self._output.clip(0.0, 255.0)


class StaticBlob(Effect):
    """Generates a blob of light. Mostly for testing purposes."""
    @staticmethod
    def getEffectDescription():
        return \
            "Generates a blob of light. Mostly for testing purposes."

    def __init__(self, spread=0.3, location=0.5):
        self.spread = spread
        self.location = location
        self.__initstate__()

    def __initstate__(self):
        # state
        super(StaticBlob, self).__initstate__()

    def __setstate__(self, state):
        # Backwards compatibility from absolute -> relative sizes
        if 'spread' in state and state['spread'] > 1:
            state['spread'] = state['spread'] / 300 / 2
        if 'location' in state and state['location'] > 1:
            state['location'] = state['location'] / 300
        return super().__setstate__(state)

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters":
            OrderedDict([
                # default, min, max, stepsize
                ("location", [0.5, 0, 1, 0.01]),
                ("spread", [0.3, 0, 1, 0.01]),
            ])
        }
        return definition

    @staticmethod
    def getParameterHelp():
        help = {"parameters": {"location": "Location where the blob is created.", "spread": "Spreading of the blob."}}
        return help

    def createBlob(self, spread_rel, location_rel):
        blobArray = np.zeros(self._num_pixels)

        # convert relative to absolute values
        spread = max(int(spread_rel * self._num_pixels), 1)
        location = int(location_rel * self._num_pixels)
        for i in range(-spread, spread + 1):
            # make sure we are in bounds of array
            if (location + i) >= 0 and (location + i) < self._num_pixels:
                blobArray[location + i] = math.cos((math.pi / spread) * i)
        return blobArray.clip(0.0, 255.0)

    def numInputChannels(self):
        return 1

    def numOutputChannels(self):
        return 1

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        if self._inputBufferValid(0):
            color = self._inputBuffer[0]
        else:
            # default: all white
            color = np.ones(self._num_pixels) * np.array([[255.0], [255.0], [255.0]])
        self._output = np.multiply(color, self.createBlob(self.spread, self.location) * np.array([[1.0], [1.0], [1.0]]))

        self._outputBuffer[0] = self._output.clip(0.0, 255.0)


class StaticWave(Effect):
    """Generates a wave of light. Mostly for testing purposes."""

    @staticmethod
    def getEffectDescription():
        return \
            "Generates a wave of light. Mostly for testing purposes."

    def __init__(self, spread=0.3, location=0.5):
        self.spread = spread
        self.location = location
        self.__initstate__()

    def __initstate__(self):
        # state
        super(StaticWave, self).__initstate__()

    def __setstate__(self, state):
        # Backwards compatibility from absolute -> relative sizes
        if 'spread' in state and state['spread'] > 1:
            state['spread'] = state['spread'] / 300 / 2
        if 'location' in state and state['location'] > 1:
            state['location'] = state['location'] / 300
        return super().__setstate__(state)

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters":
            OrderedDict([
                # default, min, max, stepsize
                ("location", [0.5, 0, 1, 0.01]),
                ("spread", [1, 0.01, 1, 0.01]),
            ])
        }
        return definition

    @staticmethod
    def getParameterHelp():
        help = {"parameters": {"location": "Location where the wave is created.", "spread": "Spreading of the wave."}}
        return help

    def getParameter(self):
        definition = self.getParameterDefinition()
        definition['parameters']['location'][0] = self.location
        definition['parameters']['spread'][0] = self.spread
        return definition

    def createBlob(self, spread_rel, location_rel):
        waveArray = np.zeros(self._num_pixels)

        # convert relative to absolute values
        spread = max(int(spread_rel * self._num_pixels), 1)
        location = int(location_rel * self._num_pixels)
        for i in range(1, spread + 1):
            # make sure we are in bounds of array
            if (location + i) >= 0 and (location + i) < self._num_pixels:
                waveArray[location + i] = spread / 20 / (i + 1)
        return waveArray.clip(0.0, 255.0)

    def numInputChannels(self):
        return 1

    def numOutputChannels(self):
        return 1

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        if self._inputBufferValid(0):
            color = self._inputBuffer[0]
        else:
            # default: all white
            color = np.ones(self._num_pixels) * np.array([[255.0], [255.0], [255.0]])
        self._output = np.multiply(color, self.createBlob(self.spread, self.location) * np.array([[1.0], [1.0], [1.0]]))

        self._outputBuffer[0] = self._output.clip(0.0, 255.0)


class GenerateWaves(Effect):
    """Effect for displaying different wave forms."""
    @staticmethod
    def getEffectDescription():
        return \
            "Effect for displaying different wave forms."

    def __init__(
            self,
            wavemode=wave_mode_default,
            period=20,
            scale=1,
    ):

        self.period = period
        self.scale = scale
        self.wavemode = wavemode
        self.__initstate__()

    def __initstate__(self):
        # state
        self._wavearray = None
        self._outputarray = []

        super(GenerateWaves, self).__initstate__()

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters":
            OrderedDict([
                # default, min, max, stepsize
                ("period", [20, 1, 300, 1]),
                ("scale", [1, 0.01, 1, 0.01]),
                ("wavemode", wave_modes),
            ])
        }
        return definition

    def getModulateableParameters(self):
        params = super().getModulateableParameters()
        params.remove('wavemode')
        return params

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "period": "Spread of one wave.",
                "scale": "Overall brightness of the effect.",
                "wavemode": "Selection of different wave forms."
            }
        }
        return help

    def getParameter(self):
        definition = super().getParameter()
        definition['parameters']['wavemode'] = [self.wavemode] + [x for x in wave_modes if x != self.wavemode]
        return definition

    def createSin(self, period, scale):
        outputarray = np.zeros(self._num_pixels)
        for i in range(0, self._num_pixels):
            outputarray[i] = 0.5 * scale - math.sin(math.pi / self.period * i) * 0.5 * scale
        return outputarray

    def createSawtooth(self, period, scale):
        outputarray = np.linspace(0, self._num_pixels, self._num_pixels)
        outputarray = 0.5 * scale - signal.sawtooth(outputarray * math.pi / self.period, width=1) * 0.5 * scale
        return outputarray

    def createSawtoothReversed(self, period, scale):
        outputarray = np.linspace(0, self._num_pixels, self._num_pixels)
        outputarray = 0.5 * scale - signal.sawtooth(outputarray * math.pi / self.period, width=0) * 0.5 * scale
        return outputarray

    def createSquare(self, period, scale):
        outputarray = np.linspace(0, self._num_pixels, self._num_pixels)
        outputarray = 0.5 * scale - signal.square(outputarray * math.pi / self.period) * 0.5 * scale
        return outputarray

    def numInputChannels(self):
        return 1

    def numOutputChannels(self):
        return 1

    async def update(self, dt):
        await super().update(dt)
        if self._num_pixels is None:
            return
        if self._wavearray is None or len(self._wavearray) != self._num_pixels:
            if self.wavemode == 'sin':
                self._wavearray = self.createSin(self.period, self.scale)
            elif self.wavemode == 'sawtooth':
                self._wavearray = self.createSawtooth(self.period, self.scale)
            elif self.wavemode == 'sawtooth_reversed':
                self._wavearray = self.createSawtoothReversed(self.period, self.scale)
            elif self.wavemode == 'square':
                self._wavearray = self.createSquare(self.period, self.scale)

    def process(self):
        if self._outputBuffer is not None:
            color = self._inputBuffer[0]
            if color is None:
                color = np.ones(self._num_pixels) * np.array([[255.0], [255.0], [255.0]])

            output = np.multiply(color, self._wavearray * np.array([[1.0], [1.0], [1.0]]))

            self._outputBuffer[0] = output.clip(0.0, 255.0)


class Sorting(Effect):
    # TODO sort like the color wheel
    """Effect for sorting an input by color or brightness."""
    @staticmethod
    def getEffectDescription():
        return \
            "Effect for sorting an input by color or brightness."

    def __init__(
            self,
            sortby=sortbydefault,
            reversed=False,
            looping=True,
    ):

        self.sortby = sortby
        self.reversed = reversed
        self.looping = looping
        self.__initstate__()

    def __initstate__(self):
        # state
        self._output = None
        self._sorting_done = True
        super(Sorting, self).__initstate__()

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters": OrderedDict([
                # default, min, max, stepsize
                ("sortby", sortby),
                ("reversed", False),
                ("looping", True)
            ])
        }
        return definition

    def getModulateableParameters(self):
        # Disable all modulations
        return []

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "sortby":
                "Parameter which the effect sorts by.",
                "reversed":
                "Flips the parameter which is sorted by.",
                "looping":
                "If activated, the effect randomly picks another parameter to sort by. "
                "If deactivated, the effects spawns a new pattern after sorting."
            }
        }
        return help

    def disorder(self):
        self._output = np.ones(self._num_pixels) * np.array([[1.0], [1.0], [1.0]])
        for i in range(self._num_pixels):
            for j in range(len(self._output)):
                self._output[j][i] = random.randint(0.0, 255.0)
        return self._output

    def bubble(self, inputArray, sortby, reversed, looping):
        if sortby == 'red':
            sortindex = 0
        elif sortby == 'green':
            sortindex = 1
        elif sortby == 'blue':
            sortindex = 2
        elif sortby == 'brightness':
            sortindex = 3
        else:
            raise NotImplementedError("Sorting not implemented.")

        if reversed:
            flip_index = -1
        else:
            flip_index = 1

        for passnum in range(len(inputArray[0]) - 1, 0, -1):
            check = 0
            for i in range(passnum):
                if sortindex == 0 or sortindex == 1 or sortindex == 2:  # sorting by color
                    if inputArray[sortindex][i] > inputArray[sortindex][i + 1 * flip_index]:
                        temp = np.array([[1.0], [1.0], [1.0]])
                        for j in range(len(inputArray)):
                            temp[j] = inputArray[j][i]
                            inputArray[j][i] = inputArray[j][i + 1 * flip_index]
                            inputArray[j][i + 1 * flip_index] = temp[j]
                    else:
                        check += 1
                        if check == passnum:
                            if looping is True:
                                self.sortby = random.choice(['red', 'green', 'blue', 'brightness'])
                                self.reversed = random.choice([True, False])
                            else:
                                self._sorting_done = True

                elif sortindex == 3:  # sorting by brightness
                    tempArray = np.sum(inputArray, axis=0)
                    if tempArray[i] > tempArray[i + 1 * flip_index]:
                        temp = np.array([[1.0], [1.0], [1.0]])
                        for j in range(len(inputArray)):
                            temp[j] = inputArray[j][i]
                            inputArray[j][i] = inputArray[j][i + 1 * flip_index]
                            inputArray[j][i + 1 * flip_index] = temp[j]
                    else:
                        check += 1
                        if check == passnum:
                            if looping is True:
                                self.sortby = random.choice(['red', 'green', 'blue', 'brightness'])
                                self.reversed = random.choice([True, False])
                            else:
                                self._sorting_done = True
            return inputArray

    def numInputChannels(self):
        return 0

    def numOutputChannels(self):
        return 1

    async def update(self, dt):
        await super().update(dt)
        if self._num_pixels is None:
            return
        if self._output is None or np.size(self._output, 1) != self._num_pixels:
            self._output = self.disorder()
            self._sorting_done = False

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return

        if self._sorting_done is True:
            self._output = self.disorder()
            self._sorting_done = False

        self._output = self.bubble(self._output, self.sortby, self.reversed, self.looping)
        self._outputBuffer[0] = self._output.clip(0.0, 255.0)


class GIFPlayer(Effect):
    @staticmethod
    def getEffectDescription():
        return \
            "Effect for displaying GIFs on LED panels."

    def __init__(self, file=None, fps=30, center_x=0.5, center_y=0.5):
        self.file = file
        self.fps = fps
        self.center_x = center_x
        self.center_y = center_y
        self.__initstate__()

    def __initstate__(self):
        super(GIFPlayer, self).__initstate__()
        self._last_show_t = 0
        self._cur_index = 0
        self._cur_image = None
        self._gif = None
        self._openGif()

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters":
            OrderedDict([
                # default, min, max, stepsize
                ("fps", [30, 0, 120, 0.1]),
                ("center_x", [0.5, 0, 1, 0.01]),
                ("center_y", [0.5, 0, 1, 0.01]),
                ("file", ['gif', None])
            ])
        }
        return definition

    def getModulateableParameters(self):
        params = super().getModulateableParameters()
        params.remove('file')
        return params

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "fps": "The number of frames per second for GIF playback.",
                "center_x": "Moves the GIF left or right if the image is being cropped.",
                "center_y": "Moves the GIF up or down if the image is being cropped.",
                "file": "The GIF to show."
            }
        }
        return help

    def numInputChannels(self):
        return 0

    def numOutputChannels(self):
        return 1

    def _openGif(self):
        adjustedFile = self.file
        if self.file is None:
            return
        if self._filterGraph is not None and self._filterGraph.getContentRoot() is not None:
            adjustedFile = os.path.join(self._filterGraph.getContentRoot(), self.file)
        try:
            self._gif = Image.open(adjustedFile)
        except Exception:
            logger.error("Cannot open file {}".format(adjustedFile))

    async def update(self, dt):
        await super().update(dt)
        if self._t - self._last_show_t > 1.0 / self.fps:
            # go to next image
            try:
                self._gif.seek(self._gif.tell() + 1)
            except Exception:
                self._openGif()

            num_cols = int(self._num_pixels / self._num_rows)
            # Resize image
            if self._gif is not None:
                self._cur_image = ImageOps.fit(self._gif.convert('RGB'), (num_cols, self._num_rows),
                                               Image.ANTIALIAS,
                                               centering=(self.center_x, self.center_y))
            # update time
            self._last_show_t = self._t

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        if self._cur_image is not None:

            img = np.asarray(self._cur_image, dtype=np.uint8)
            img = img.reshape(-1, img.shape[-1]).T
            self._outputBuffer[0] = img
