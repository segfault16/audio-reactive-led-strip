from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import numpy as np
import pyaudio
from audioled.filtergraph import Effect

def _open_input_stream(device_index=None, channels = 1):
    """Opens a PyAudio audio input stream

    Parameters
    ----------
    device_index: int, optional
        Device index for the PyAudio audio input stream.
        If device index is not specified then the default audio device
        will be opened.
    """
    p = pyaudio.PyAudio()
    defaults = p.get_default_host_api_info()
    if device_index is None:
        device_index = defaults['defaultInputDevice']
    device_info = p.get_device_info_by_index(device_index)

    if device_info['maxInputChannels'] == 0:
        err = 'Your audio input device cannot be opened. '
        err += 'Change default audio device or try a different device index. '
        err += 'Device info:\n{}\n{}'.format(defaults, device_info)
        raise OSError(err)

    try:
        stream = p.open(format=pyaudio.paFloat32,
                        channels=channels,
                        rate=int(device_info['defaultSampleRate']),
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=0)
    except OSError as e:
        err = 'Error occurred while attempting to open audio device. '
        err += 'Check your operating system\'s audio device configuration. '
        err += 'Audio device information: \n'
        err += str(device_info)
        print(err)
        raise e
    return stream, int(device_info['defaultSampleRate'])


def stream_audio(chunk_rate=60, ignore_overflows=True, device_index=None, channels = 1):
    audio_stream, samplerate = _open_input_stream(device_index, channels)
    chunk_length = int(samplerate // chunk_rate)

    def audio_chunks():
        stream = audio_stream
        fs = samplerate
        while True:
            try:
                chunk = stream.read(chunk_length)
            except IOError as e:
                if e.errno == pyaudio.paInputOverflowed:
                    print('Audio buffer full')
                    if ignore_overflows:
                        stream, fs = _open_input_stream(device_index)
                        continue
                    else:
                        raise e
            chunk = np.fromstring(chunk, np.float32).astype(np.float)
            yield chunk
    return audio_chunks(), samplerate


def print_audio_devices():
    """Print information about the system's audio devices"""
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        print(info['name'])
        print('\tDevice index:', info['index'])
        print('\tSample rate:', info['defaultSampleRate'])
        print('\tMax input channels:', info['maxInputChannels'])
        print('\tMax output channels:', info['maxOutputChannels'])
    p.terminate()

def numInputChannels(device_index=None):
    p = pyaudio.PyAudio()
    device = device_index
    defaults = p.get_default_host_api_info()
    if device_index is None:
        device= defaults['defaultInputDevice']
    info = p.get_device_info_by_index(device)
    return info['maxInputChannels']

class AudioInput(Effect):
    """
    Outputs:
    0: Audio Channel 0
    1: Audio Channel 1...
    
    """
    def __init__(self, device_index=None):
        self.device_index = device_index
        self._outputBuffer = None
        self._inputBuffer = None
        self._audioStream, self._sampleRate = stream_audio()
        super(AudioInput, self).__init__()

    def numOutputChannels(self):
        return numInputChannels(self.device_index)
    
    def numInputChannels(self):
        return 0

    def getSampleRate(self):
        return self._sampleRate

    def setOutputBuffer(self, buffer):
        self._outputBuffer = buffer

    def setInputBuffer(self, buffer):
        self._inputBuffer = buffer

    def process(self):
        chunks = next(self._audioStream)
        self._outputBuffer[0] = chunks