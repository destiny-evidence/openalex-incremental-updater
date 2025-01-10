"""Load the package version from the package metadata."""

from importlib.metadata import PackageNotFoundError, version


def get_package_version(package_name: str) -> str:
    """
    Get the version of a package.

    Args:
        package_name (str): The name of the package as a string.

    Returns:
        str: Package version as a string.

    """
    placeholder_version_number = "0.999.999"
    try:
        return version(package_name)
    except PackageNotFoundError:
        return placeholder_version_number
