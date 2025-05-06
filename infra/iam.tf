data "aws_iam_policy_document" "glue_assume"{
    statement {
        actions = ["sts:AssumeRole"]
        principals {
            type = "Service"
            identifiers = ["glue.amazonaws.com"]
        }
    }
}

resource "aws_iam_role" "glue_role"{
    name = "SkuSenseGlueRole"
    assume_role_policy = data.aws_iam_policy_document.glue_assume.json
}

resource "aws_iam_policy" "glue_s3_access" {
    name = "SkuSenseGlueS3Access"
    policy = jsonencode ({
        Version = "2012-10-17",
        Statement = [{
            Action = [
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket"
            ],
            Effect = "Allow",
            Resource = [
                aws_s3_bucket.raw_data.arn,
                "${aws_s3_bucket.raw_data.arn}/*"
            ]
        }]
    })
}

resource "aws_iam_role_policy_attachment" "attach_s3"{
    role = aws_iam_role.glue_role.name
    policy_arn = aws_iam_policy.glue_s3_access.arn
}
