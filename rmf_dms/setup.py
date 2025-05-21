from setuptools import find_packages, setup

package_name = "rmf_dms"

setup(
    name=package_name,
    version="1.0.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="speed",
    maintainer_email="speed@docker.com",
    description="TODO: Package description",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "dms_communicator = rmf_dms.dms_communicator:main",
            "fake_dms = rmf_dms.fake_dms:main",
            "debug_preparing = rmf_dms.debug_preparing:main",
            "task_sender = rmf_dms.task_sender:main",
        ],
    },
)
