# Copyright (c) 2020 SUSE LINUX GmbH
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import os
import time


def test_file_creation(rook_cluster):
    # Create direct-mount deployment
    rook_cluster.kubernetes.kubectl_apply(
        os.path.join(rook_cluster.ceph_dir, 'direct-mount.yaml'))

    time.sleep(5)

    # Mount myfs in pod and put a test string into a file
    rook_cluster.kubernetes.execute_in_pod_by_label("""
        # Create the directory
        mkdir /tmp/registry

        # Detect the mon endpoints and the user secret for the connection
        mon_endpoints=$(grep mon_host /etc/ceph/ceph.conf | awk '{print $3}')
        my_secret=$(grep key /etc/ceph/keyring | awk '{print $3}')

        # Mount the filesystem
        mount -t ceph -o mds_namespace=myfs,name=admin,secret=$my_secret \
            $mon_endpoints:/ /tmp/registry

        # See your mounted filesystem
        df -h /tmp/registry

        echo "Hello Rook" > /tmp/registry/hello
        umount /tmp/registry
        rmdir /tmp/registry
    """, label="rook-direct-mount")

    # Scale the direct mount deployment down and back up again to recreate the
    # pod (to ensure that we haven't left anything on the container volume
    # and therefore to be sure we are writing to the cephfs)
    rook_cluster.kubernetes.kubectl(
        "scale deployment rook-direct-mount --replicas=0 -n rook-ceph")

    time.sleep(5)

    rook_cluster.kubernetes.kubectl(
        "scale deployment rook-direct-mount --replicas=1 -n rook-ceph")

    time.sleep(5)

    # Mount myfs again and output the contents
    result = rook_cluster.kubernetes.execute_in_pod_by_label("""
        # Create the directory
        mkdir /tmp/registry

        # Detect the mon endpoints and the user secret for the connection
        mon_endpoints=$(grep mon_host /etc/ceph/ceph.conf | awk '{print $3}')
        my_secret=$(grep key /etc/ceph/keyring | awk '{print $3}')

        # Mount the filesystem
        mount -t ceph -o mds_namespace=myfs,name=admin,secret=$my_secret \
            $mon_endpoints:/ /tmp/registry

        cat /tmp/registry/hello
        umount /tmp/registry
        rmdir /tmp/registry
    """, label="rook-direct-mount")

    # Assert that the contents is as expected, confirming that writing to the
    # cephfs is working as expected
    assert result.stdout.strip() == "Hello Rook"

    # Cleanup: Uninstall rook-direct-mount
    rook_cluster.kubernetes.kubectl(
        "delete deployment.apps/rook-direct-mount -n rook-ceph")
