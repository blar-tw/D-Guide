from setuptools import find_packages, setup

package_name = 'path_planning'

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
    description='Google Maps Directions to ROS 2 waypoint service for D-Guide',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'pp_node = path_planning.pp_node:main',
        ],
    },
)