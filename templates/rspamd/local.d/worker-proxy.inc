milter = yes;
timeout = 120s;
upstream "local" {
  default = yes;
  self_scan = yes;
}
spam_header = "X-Spam";