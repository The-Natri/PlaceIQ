export function homeRouteFor(role) {
  return role === "student" ? "/student" : "/admin";
}
