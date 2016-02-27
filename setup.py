from setuptools import setup


setup(name='CorpFin',
      version='0.0.0',
      packages=['CorpFin'],
      url='https://github.com/MBALearnsToCode/CorpFin',
      author='Vinh Luong (a.k.a. MBALearnsToCode)',
      author_email='MBALearnsToCode@UChicago.edu',
      description='Corporate Finance functionalities based on SymPy and Theano',
      long_description='(please read README.md on GitHub)',
      license='MIT License',
      install_requires=['namedlist', 'NumPy', 'Pandas', 'SymPy', 'Theano'],
      classifiers=[],   # https://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='corporate finance corp fin financial sympy theano')
