from setuptools import setup


setup(name='FinSymPy',
      version='0.0.0',
      packages=['FinSymPy'],
      url='https://github.com/MBALearnsToCode/FinSymPy',
      author='Vinh Luong (a.k.a. MBALearnsToCode)',
      author_email='MBALearnsToCode@UChicago.edu',
      description='Financial functions based on SymPy and Theano',
      long_description='(please read README.md on GitHub)',
      license='MIT License',
      install_requires=['NumPy', 'SymPy', 'Theano'],
      classifiers=[],   # https://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='financial sympy theano')
