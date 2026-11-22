// GASL's own inert isolation canary. It never imports or executes third-party Skills.
// Build statically (CGO_ENABLED=0), place in a FROM scratch image, and run with
// a non-privileged UID and a strict Docker policy on an ephemeral Linux runner.
package main

import (
	"encoding/json"
	"fmt"
	"net"
	"os"
	"strconv"
	"strings"
	"time"
)

const fixtureText = "GASL_INERT_TEST_FIXTURE_V1\n"

func statusField(field string) string {
	content, err := os.ReadFile("/proc/self/status")
	if err != nil {
		return ""
	}
	for _, line := range strings.Split(string(content), "\n") {
		if strings.HasPrefix(line, field+":") {
			return strings.TrimSpace(strings.TrimPrefix(line, field+":"))
		}
	}
	return ""
}

func mountHasOptions(mountPath string, required ...string) bool {
	contents, err := os.ReadFile("/proc/self/mountinfo")
	if err != nil {
		return false
	}
	for _, line := range strings.Split(string(contents), "\n") {
		fields := strings.Fields(line)
		if len(fields) < 10 || fields[4] != mountPath {
			continue
		}
		present := map[string]bool{}
		for _, option := range strings.Split(fields[5], ",") {
			present[option] = true
		}
		for _, option := range required {
			if !present[option] {
				return false
			}
		}
		return true
	}
	return false
}

func scratchIsBoundedTmpfs() bool {
	contents, err := os.ReadFile("/proc/self/mountinfo")
	if err != nil {
		return false
	}
	for _, line := range strings.Split(string(contents), "\n") {
		fields := strings.Fields(line)
		if len(fields) < 10 || fields[4] != "/tmp" {
			continue
		}
		if !mountHasOptions("/tmp", "rw", "nosuid", "nodev", "noexec") {
			return false
		}
		for i, field := range fields {
			if field == "-" && len(fields) > i+1 {
				return fields[i+1] == "tmpfs"
			}
		}
	}
	return false
}

func noExternalInterfaces() bool {
	interfaces, err := net.Interfaces()
	if err != nil {
		return false
	}
	for _, iface := range interfaces {
		if iface.Flags&net.FlagLoopback == 0 {
			return false
		}
	}
	return true
}

func networkDenied() bool {
	conn, err := net.DialTimeout("tcp", "1.1.1.1:443", 750*time.Millisecond)
	if conn != nil {
		_ = conn.Close()
	}
	return err != nil
}

func cgroupMemoryBounded() bool {
	text, err := os.ReadFile("/sys/fs/cgroup/memory.max")
	if err != nil {
		return false
	}
	value, err := strconv.ParseInt(strings.TrimSpace(string(text)), 10, 64)
	return err == nil && value > 0 && value <= 128*1024*1024
}

func cgroupPidsBounded() bool {
	text, err := os.ReadFile("/sys/fs/cgroup/pids.max")
	if err != nil {
		return false
	}
	value, err := strconv.ParseInt(strings.TrimSpace(string(text)), 10, 64)
	return err == nil && value > 0 && value <= 64
}

func cgroupCPUBounded() bool {
	text, err := os.ReadFile("/sys/fs/cgroup/cpu.max")
	if err != nil {
		return false
	}
	fields := strings.Fields(string(text))
	if len(fields) != 2 {
		return false
	}
	quota, e1 := strconv.ParseInt(fields[0], 10, 64)
	period, e2 := strconv.ParseInt(fields[1], 10, 64)
	return e1 == nil && e2 == nil && period > 0 && quota > 0 && quota <= period/2
}

func noLeakedEnvironment() bool {
	allowed := map[string]bool{"PATH": true, "HOSTNAME": true, "GASL_CANARY": true, "HOME": true}
	if os.Getenv("HOME") != "/nonexistent" {
		return false
	}
	if os.Getenv("GASL_CANARY") != "INERT_ONLY" {
		return false
	}
	for _, item := range os.Environ() {
		key, _, _ := strings.Cut(item, "=")
		if !allowed[key] {
			return false
		}
	}
	return true
}

func isDeniedWrite(path string) bool {
	err := os.WriteFile(path, []byte("GASL_CANNOT_WRITE"), 0600)
	if err == nil {
		_ = os.Remove(path)
		return false
	}
	return true
}

func scratchWritable() bool {
	path := "/tmp/gasl-canary-small"
	err := os.WriteFile(path, []byte("scratch"), 0600)
	if err != nil {
		return false
	}
	defer os.Remove(path)
	return true
}

func scratchSizeBounded() bool {
	file, err := os.Create("/tmp/gasl-canary-size")
	if err != nil {
		return false
	}
	defer os.Remove(file.Name())
	defer file.Close()
	chunk := make([]byte, 1024*1024)
	for i := 0; i < 10; i++ {
		if _, err = file.Write(chunk); err != nil {
			return i >= 7
		}
	}
	return false
}

func missingHostAssets() bool {
	for _, path := range []string{"/var/run/docker.sock", "/root/.ssh", "/home/runner", "/Users", "/host-only-canary-secret"} {
		if _, err := os.Lstat(path); !os.IsNotExist(err) {
			return false
		}
	}
	return true
}

func main() {
	checks := map[string]bool{}
	checks["pinned_read_only_input"] = func() bool {
		content, err := os.ReadFile("/skill/pinned.txt")
		return err == nil && string(content) == fixtureText &&
			mountHasOptions("/skill", "ro") && isDeniedWrite("/skill/pinned.txt")
	}()
	checks["root_filesystem_read_only"] = mountHasOptions("/", "ro") && isDeniedWrite("/gasl-root-write-probe")
	checks["network_access_denied"] = networkDenied()
	checks["network_namespace_has_only_loopback"] = noExternalInterfaces()
	checks["scratch_tmpfs_restricted_mount"] = scratchIsBoundedTmpfs()
	checks["unprivileged_uid_gid"] = os.Getuid() == 65532 && os.Getgid() == 65532
	checks["private_pid_namespace_verified"] = os.Getpid() == 1
	checks["capabilities_dropped"] = strings.HasPrefix(statusField("CapEff"), "0000000000000000")
	checks["no_new_privileges"] = strings.HasPrefix(statusField("NoNewPrivs"), "1")
	checks["seccomp_filter_active"] = strings.HasPrefix(statusField("Seccomp"), "2")
	checks["no_unexpected_environment"] = noLeakedEnvironment()
	checks["no_docker_socket_or_host_home"] = missingHostAssets()
	checks["fixture_symlink_cannot_escape_to_host"] = func() bool {
		_, err := os.ReadFile("/skill/escape-to-host")
		return os.IsNotExist(err)
	}()
	checks["scratch_writable"] = scratchWritable()
	checks["scratch_size_bounded"] = scratchSizeBounded()
	checks["memory_cgroup_bounded"] = cgroupMemoryBounded()
	checks["pids_cgroup_bounded"] = cgroupPidsBounded()
	checks["cpu_cgroup_bounded"] = cgroupCPUBounded()

	passed := true
	for _, value := range checks {
		if !value {
			passed = false
		}
	}
	payload := map[string]interface{}{
		"schema_version":            "gasl-inert-canary-1",
		"passed":                    passed,
		"checks":                    checks,
		"third_party_code_executed": false,
		"skills_installed":          false,
	}
	encoded, err := json.Marshal(payload)
	if err != nil {
		fmt.Fprintln(os.Stderr, "cannot serialize canary result")
		os.Exit(2)
	}
	fmt.Println(string(encoded))
	if !passed {
		os.Exit(1)
	}
}
