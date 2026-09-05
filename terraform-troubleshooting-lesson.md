# Terraform and AWS Infrastructure Drift: Troubleshooting Lesson

## Incident Summary

A Terraform deployment encountered several AWS errors:

- ECS cluster deletion failed because an ECS service was still active.
- The ALB and target group already existed when Terraform tried to create them.
- The CloudWatch log group and IAM roles already existed.
- The GitHub Actions OIDC provider already existed.
- The target group could not be deleted because the ALB listener still referenced it.
- The ALB rejected Terraform's security group because it belonged to a different VPC.

The common cause was **infrastructure drift**: AWS resources and Terraform state did not describe the same infrastructure.

## Core Concepts

### Terraform configuration is not Terraform state

Terraform uses three sources of information:

1. Configuration: the `.tf` files describing the desired infrastructure.
2. State: the resources Terraform believes it manages.
3. Provider data: the resources that actually exist in AWS.

A resource can exist in AWS but be absent from Terraform state. In that case, Terraform attempts to create it and AWS returns an `already exists` error.

A resource can also exist in Terraform state but have been changed or replaced outside Terraform. In that case, Terraform may try to modify it using stale identifiers.

### Resource dependencies control destroy order

AWS resources often have strict dependency rules. For this deployment:

```text
ECS service -> ECS cluster
ALB listener -> target group -> ALB
```

Terraform normally calculates these dependencies from references such as:

```terraform
cluster = aws_ecs_cluster.medical_rag_cluster.id
```

However, Terraform can only destroy a resource first if that resource is present in the same state. An ECS service deployed by GitHub Actions but missing from Terraform state can remain active while Terraform tries to delete the cluster.

## Error 1: ECS Cluster Contains Services

### Error

```text
ClusterContainsServicesException:
The Cluster cannot be deleted while Services are active.
```

### Meaning

The ECS cluster still contains an active service. The cluster cannot be deleted until the service is deleted or scaled and removed.

### Diagnosis

Check the service directly:

```powershell
aws ecs describe-services `
  --cluster medical-rag-cluster `
  --services medical-rag-ecs `
  --region eu-north-1
```

Check whether Terraform manages it:

```powershell
terraform -chdir=terraform state list | Select-String ecs
```

If AWS shows the service but the state does not, this is state drift.

### Recovery options

If the service should be destroyed:

```powershell
aws ecs delete-service `
  --cluster medical-rag-cluster `
  --service medical-rag-ecs `
  --force `
  --region eu-north-1
```

If the service should remain Terraform-managed, import it instead:

```powershell
terraform -chdir=terraform import `
  aws_ecs_service.medical_rag_ecs `
  medical-rag-cluster/medical-rag-ecs
```

Do not add a lifecycle block as a workaround. The issue is missing state, not an incorrect lifecycle policy.

## Error 2: Resource Already Exists

### Errors

```text
ELBv2 Load Balancer already exists
ELBv2 Target Group already exists
ResourceAlreadyExistsException: The specified log group already exists
EntityAlreadyExists: Role with name ecs-task-execution-role already exists
EntityAlreadyExists: Provider with url ... already exists
```

### Meaning

These AWS resources already exist, but Terraform was not managing them in the active state.

### Correct response: import, do not recreate

First find the provider-specific identifier, then import the resource.

Examples:

```powershell
terraform -chdir=terraform import `
  aws_lb.main_alb `
  arn:aws:elasticloadbalancing:eu-north-1:431451851290:loadbalancer/app/main-alb/d2757ed9a531ffa3

terraform -chdir=terraform import `
  aws_lb_target_group.medical_task_tg `
  arn:aws:elasticloadbalancing:eu-north-1:431451851290:targetgroup/medical-task-tg/0586e35f5070d12b

terraform -chdir=terraform import `
  aws_cloudwatch_log_group.medical_rag `
  /ecs/medical-rag

terraform -chdir=terraform import `
  aws_iam_role.ecs_task_execution `
  ecs-task-execution-role

terraform -chdir=terraform import `
  aws_iam_openid_connect_provider.github `
  arn:aws:iam::431451851290:oidc-provider/token.actions.githubusercontent.com
```

Importing updates Terraform state. It does not create or delete the AWS resource.

## Error 3: Target Group Is Still in Use

### Error

```text
ResourceInUse:
Target group is currently in use by a listener or a rule
```

### Meaning

The ALB listener still forwards traffic to the target group. AWS will not delete the target group first.

### Correct dependency order

Delete resources in this order:

```text
ECS service
  -> ALB listener
    -> target group
      -> ALB
```

For manual cleanup:

```powershell
aws elbv2 delete-listener `
  --listener-arn <listener-arn> `
  --region eu-north-1

aws elbv2 delete-load-balancer `
  --load-balancer-arn <load-balancer-arn> `
  --region eu-north-1

aws elbv2 delete-target-group `
  --target-group-arn <target-group-arn> `
  --region eu-north-1
```

The listener must be removed before the target group. The load balancer can then be removed before the target group is deleted, depending on the specific AWS resource relationships and current state.

When Terraform manages all resources in one consistent state, its dependency graph should perform this ordering automatically.

## Error 4: Invalid Security Group on the ALB

### Error

```text
InvalidConfigurationRequest:
One or more security groups are invalid
```

### Actual cause

The ALB was in one VPC, while Terraform attempted to attach a security group from another VPC.

Observed values:

| Resource | VPC |
|---|---|
| Terraform-managed ALB security group `sg-04d4229720f59f659` | `vpc-0f34f36ee12ff0a0f` |
| Live ALB security group `sg-09439cd157b7c73ab` | `vpc-03fb2c8814db2a67b` |
| Live ALB and target group | `vpc-03fb2c8814db2a67b` |

An ALB can only use security groups from its own VPC. A security group from a different VPC is invalid even if the group name is the same.

### Useful checks

```powershell
aws elbv2 describe-load-balancers `
  --names main-alb `
  --region eu-north-1 `
  --query 'LoadBalancers[0].{Vpc:VpcId,SecurityGroups:SecurityGroups}'

aws ec2 describe-security-groups `
  --group-ids <security-group-id> `
  --region eu-north-1 `
  --query 'SecurityGroups[].{Id:GroupId,Vpc:VpcId,Name:GroupName}'

terraform -chdir=terraform plan -refresh-only
```

A refresh-only plan is useful because it reads AWS and shows drift without changing remote infrastructure.

### Safe response during destruction

If the goal is to destroy the live infrastructure and Terraform has imported resources from a different VPC, do not run `terraform apply` to force the mismatch. Remove the live ALB dependencies manually, then remove those objects from Terraform state:

```powershell
terraform -chdir=terraform state rm `
  aws_lb_listener.lb_listener `
  aws_lb.main_alb `
  aws_lb_target_group.medical_task_tg
```

Then continue with `terraform destroy` for the remaining resources.

## A Reliable Troubleshooting Workflow

### 1. Stop and identify the operation

Determine whether Terraform is applying, destroying, refreshing, or importing. Avoid running overlapping Terraform commands against the same state.

```powershell
Get-Process terraform
```

A state lock usually means another Terraform process is still active.

### 2. Inspect Terraform state

```powershell
terraform -chdir=terraform state list
```

Compare the list with the resources declared in the `.tf` files.

### 3. Inspect AWS directly

Use AWS CLI commands to verify whether the resource exists, which VPC it belongs to, and what depends on it.

Examples:

```powershell
aws ecs describe-services ...
aws elbv2 describe-load-balancers ...
aws elbv2 describe-listeners ...
aws elbv2 describe-target-groups ...
aws ec2 describe-security-groups ...
```

### 4. Classify the mismatch

- Exists in AWS, absent from state: import or intentionally delete it.
- Exists in state, absent from AWS: refresh state and let Terraform recreate it if appropriate.
- Exists in both but identifiers differ: investigate replacement or wrong state/root.
- Same name but different VPC: do not apply until the VPC ownership is resolved.

### 5. Use refresh-only planning

```powershell
terraform -chdir=terraform plan -refresh-only
```

This is a low-risk way to reveal out-of-band changes.

### 6. Reconcile one root and one state

The long-term fix is to ensure that:

- There is one Terraform root directory for the deployment.
- All resources are managed from one state file or an intentionally designed set of states.
- CI/CD does not create resources that Terraform also believes it owns.
- GitHub Actions updates task definitions and ECS services consistently with Terraform ownership.
- Resource names and VPC inputs are not reused across separate deployments accidentally.

## Key Lessons to Remember

1. `already exists` usually means missing Terraform state, not that the Terraform resource is invalid.
2. Import existing resources before applying changes to them.
3. AWS deletion errors often reveal the dependency that must be removed first.
4. An ALB, target group, subnet, and security group must belong to compatible VPCs.
5. Same-name resources can still be different resources in different VPCs.
6. `terraform plan -refresh-only` is a valuable diagnostic tool.
7. Never use `terraform apply` to force a known cross-VPC mismatch.
8. Keep resource ownership clear: Terraform should manage infrastructure, while CI/CD should deploy application revisions through an agreed workflow.
9. Check for active Terraform processes before troubleshooting state-lock or partial-operation symptoms.

## Quick Diagnostic Checklist

- [ ] Is another Terraform process running?
- [ ] Does the resource exist in Terraform state?
- [ ] Does the resource exist in AWS?
- [ ] Is the AWS identifier correct?
- [ ] Is the resource in the expected region?
- [ ] Is it in the expected VPC?
- [ ] Are dependent resources still attached?
- [ ] Was the resource created by CI/CD or manually?
- [ ] Should it be imported, deleted, or left unmanaged?
- [ ] Did a refresh-only plan confirm the expected state?
