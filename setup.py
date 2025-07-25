"""Setup configuration for Vitalis Chatbot."""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="vitalis-chatbot",
    version="1.0.0",
    author="Vitalis Stream",
    description="WhatsApp chatbot integration with GoHighLevel for appointment scheduling",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Vitalis-Stream/vitalis-chatbot-1.0",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "vitalis-chatbot=app.__main__:main",
        ],
    },
)