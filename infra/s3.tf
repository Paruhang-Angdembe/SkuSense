resource "random_id" "suffix" {
    byte_length = 4
}

resource "aws_s3_bucket" "raw_data" {
    bucket = "skusense-raw-data-${random_id.suffix.hex}"
    acl = "private"

    versioning {
        enabled = true
    }
}

