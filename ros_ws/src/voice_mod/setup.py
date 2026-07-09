from setuptools import find_packages, setup

package_name = 'voice_mod'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name, ['models/ww.ppn'])
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Blar',
    maintainer_email='blar@example.com',
    description='Voice interface for D-Guide: wake word detection, speech-to-text, and LLM command parsing',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'ww_node_service = voice_mod.ww_node_service:main',
            'ww_node_topic = voice_mod.ww_node_topic:main',
            'llm_node = voice_mod.llm_node:main',
        ],
    },
)
