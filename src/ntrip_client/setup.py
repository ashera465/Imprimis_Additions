from setuptools import find_packages, setup

package_name = 'ntrip_client'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='asher-abraham',
    maintainer_email='abrahama5@vcu.edu',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        # Alias = executable path
        'console_scripts': [
            'ntrip_node = ntrip_client.ntrip_node:main'
        ],
    },
)
