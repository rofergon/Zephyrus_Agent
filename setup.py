from setuptools import setup, find_packages

setup(
    name="zephyrus_agent",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp==3.9.3",
        "websockets==15.0",
        "python-dotenv==1.0.1",
        "python-json-logger==2.0.7",
        "schedule==1.2.1",
        "openai==1.61.1",
        "pydantic==2.6.1"
    ],
) 