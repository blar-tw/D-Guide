from setuptools import find_packages, setup

package_name = 'mission_manager'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Blar',
    maintainer_email='blar@example.com',
    description='Mission orchestration for D-Guide: command input and waypoint-following flight',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'control_node = mission_manager.control_node:main',
            'followpp_server = mission_manager.followpp_server:main',
        ],
    },
)
