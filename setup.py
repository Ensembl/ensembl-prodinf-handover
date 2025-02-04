# .. See the NOTICE file distributed with this work for additional information
#    regarding copyright ownership.
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#        http://www.apache.org/licenses/LICENSE-2.0
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
import os
from pathlib import Path
from setuptools import setup, find_namespace_packages, find_packages

with open(Path(__file__).parent / 'README.md') as f:
    readme = f.read()
with open(Path(__file__).parent / 'VERSION') as f:
    version = f.read()


def import_requirements():
    """Import ``requirements.txt`` file located at the root of the repository."""
    with open(Path(__file__).parent / 'requirements.txt') as file:
        return [line.rstrip() for line in file.readlines()]



setup(
    name='handover',
    version=os.getenv('CI_COMMIT_TAG', version),
    namespace_packages=['ensembl'],
    packages=find_namespace_packages(where='src', include=['ensembl.*']),
    package_dir={'': 'src'}, 
    include_package_data=True,   
    url='https://github.com/Ensembl/ensembl-prodinf-handover',
    license='APACHE 2.0',
    author='Vinay Kaikala, Marc Chakiachvili',
    author_email='vinay@ebi.ac.uk, mchakiachvili@ebi.ac.uk',
    maintainer='Ensembl Production Team',
    maintainer_email='ensembl-production@ebi.ac.uk',
    description='Ensembl handover service',
    python_requires='>=3.10',
    install_requires=import_requirements(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Utilities",
        "Topic :: System :: Distributed Computing",
    ],
    keywords='ensembl, handover, production',
)
