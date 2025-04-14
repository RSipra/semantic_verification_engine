from setuptools import setup, find_packages

# Read dependencies from requirements.txt
with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name='hptrivia-game',
    version='0.1.0',
    description='Harry Potter command-line trivia game',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=requirements + ['setuptools'],  # Ensures setuptools is installed
    entry_points={
        'console_scripts': [
            'hptrivia=main:main',
        ],
    },
    python_requires='>=3.8',
)
