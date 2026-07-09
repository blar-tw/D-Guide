from setuptools import find_packages, setup

package_name = 'obstacle_avoidance'

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
    description='HOLO-DWA reactive obstacle avoidance for D-Guide: LiDAR-driven '
                'Dynamic Window Approach flight executor (ArduPilot GUIDED via MAVLink)',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'dwa_navigator = obstacle_avoidance.dwa_navigator:main',
        ],
    },
)
