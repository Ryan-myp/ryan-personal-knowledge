from setuptools import setup, find_packages

setup(
    name="ad-agent",
    version="1.0.0",
    description="多渠道广告投放 Agent - 单 Agent + 多 Skills 架构",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Ryan",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "requests>=2.28.0",
        "pyjwt>=2.6.0",
        "PyYAML>=6.0",
        "fastapi>=0.100.0",
        "uvicorn>=0.22.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
