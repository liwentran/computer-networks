# Part 1

## Question 1
**a. Given the current contents of the IP forwarding table, what do you suspect will happen when you attempt to send an IP datagram from a to b (10.0.0.2)?**

The content of the forwarding table is shown in the following code block:
```
10.0.0.0/24 dev a-s1 proto kernel scope link src 10.0.0.1
```
This entry means that any IP destination that matches `10.0.0.0/24` will be sent to `a-s1`, and this entry has no next hop. 

When you send a IP datagram from `a` to `b` (destination IP = `10.0.0.2`), it will match with the network range specified by `10.0.0.0/24`, so it will be sent to `a-s1`. The last part says that the source IP will be set to `10.0.0.1`. Because `b` is under the same subnet, it should directly be sent to `b` without further routing.

**b. Given the current contents of the IP forwarding table, what do you suspect will happen when you attempt to send an IP datagram from a to c (10.0.1.2)?**

`10.0.1.2` does not match with `10.0.0.0/24`, so the packet will not be sent to `a-s1`. Because there are no other remainint entries in the forwarding table, the the device will send it to the default route. However, since no default route is specified, it is dropped. 

**c. What are the current contents of a's ARP table?**

ARP's functionality is to translate IP addresses to physcial addresses. In the case of `a`, we should expect see its IP address (`10.0.0.1`) and a corresponding MAC address (`fe:41:41:0c:ab:f8`), which we find from running `ip addr 2> /dev/null` on host `a`.

## Question 2
The Wireshark window after `ping -c 1 -W 1 10.0.0.2` from host `a`.
![Alt text](exercises-2-wireshark.png)
**a. Consider the very first (in terms of time) frame sent from `a`. What was the protocol and the purpose of the packet carried by that frame?**

![Alt text](exercise-2a-request.png)
The first frame sent from `a` was an Address Response Protocol (ARP) request. The purpose of this packet is to broadcast (`ff:ff:ff:ff:ff:ff`) to all the devices on the network to ask for the MAC address of the device associated with the IP address `10.0.0.2`, which is the target IP address. Essentially, its goal is to resolve the MAC address from an IP address. 

**b. Which of all the hosts or routers connected to s1 or s2 observed this first frame from a? Use the rows in the "packet list" window to answer the question.**

Host `b` and router `r1` observed the first frame.

**c. Briefly explain your answer to part b. That is, why did this set of hosts get the frame (no more, no less)?**

The message traversed the interfaces `s1-a`, `s1-b`, `s1-r1`. The first interface traversed was  `s1-a`, so `s1` interface will broadcast it to all its connected nodes (`r1` via `s1-r1` and `b` via `s1-b`). When it sent it to host `b` with MAC address (`96:8b:23:91:12:f0`), it will find that its IP address (`10.0.0.2/24`) matches `10.0.0.2`, which was the target IP of the ARP request sent out; however, this is the last node, so it will not send it anywhere else. When the broadcast was sent to `s1-r1`, this router found no other matches in its routing table besides `s1`, which is why no other hosts will get the frame. 

**d. Which of all the hosts or routers connected to s1 or s2 observed the response from from b?**

Host `a` observed the response from `b`.

**e. Briefly explain your answer to part d. That is, why did this set of hosts get the frame (no more, no less)?**

The response first traversed the interface `s1-a`. Since host `b`'s response is intended to send to its target IP `10.0.0.1`, the interface `s1` would have found a match in its routing table to send on the link `s1-a`. Since this is the only host that matches this desired IP address, host `a` will be the only one that responds.

**f. Was the ping successful? That is, did you get a response?**

![Alt text](exercise-2f-ping-response.png)
The ping was successful. Host `a` received a response. Host `b` sent it the rtt of the interaction and a few othehr details. The response is shown in the screenshot above. 

## Question 3
**What entries are in the table when you re-run the `ip neigh` command to see the new state of a's ARP table?**

![Alt text](exercise-3-ARP-table.png)
The new ARP table has one entry: `10.0.0.2 dev a-s1 lladdr 96:8b:23:91:12:f0 REACHABLE` which associates the IP address `10.0.0.2` with the MAC address `96:8b:23:91:12:f0`. This table entry was added because of the ARP request and response. 


## Question 4
Now run the following command on `a` to send a single packet from `a` to `c`: `ping -c 1 -W 1 10.0.1.2`

**a. Was the ping successful? That is, did you get a response?**
The ping was not successful because there was no response. It says that `Network is unreachable`.

**b. Which of all the hosts or routers connected to s1 or s2 observed frame(s) associated with the ping command you just issued?**
None of the frames observed the frames associated with the ping. This is because there is no entry in the routing table that would match with `10.0.1.2`. However, if there was a route, host `c` would have responded.

## Question 5

**Identify the IP prefix, the next hop IP address, and the outgoing interface to create a default route for `a` using `r1`. Then add that entry to `a`'s forwarding table, using the command and description above. Show the command that you used.**

The IP prefix needs to be the default route which is `0.0.0.0/0`, the next hop IP address should be of `s1` which is `10.0.0.3` because this is the address to reach `r1` from `s1`, and interface is `a-s1`. Therefore the command must be: `sudo ip route add 0.0.0.0/0 via 10.0.0.3 dev a-s1`

## Question 6
Again, run the following command on `a` to send a single packet from `a` to `c`: `ping -c 1 -W 1 10.0.1.2`

**a. Consider the very first (in terms of time) frame sent from `r1` on `r1-s2`. What was the protocol and the purpose of the packet carried by that frame?**
The first frame sent from `r1` on `r1-s2` is an ARP Request. The purpose of this packet is to broadcast (`ff:ff:ff:ff:ff:ff`) to all the devices on the network to ask for the MAC address of the device associated with the IP address `10.0.1.2`, which is the target IP address. Essentially, its goal is to resolve the MAC address from an IP address. Before this moment, we had found the MAC address of router `r1`, so then the request was sent to `r1`, but `r1` doesn't know the MAC address of `10.0.0.2` which is why it sent this ARP Request.

**b. Which of all the hosts or routers connected to s1 or s2 observed this frame from r1? Use the rows in the "packet list" window to answer the question.**
Host `c` and `d`. 

**c. Briefly explain your answer to part b. That is, why did this set of hosts get the frame (no more, no less)? Hint: think about purpose of the packet, look at the addresses in the Ethernet frame header, and consider the makeup of the network.**

At this point, router `r1` knows it has to forward its request to `10.0.1.2`, but it needs to broadcast the ARP request to find the MAC address of this IP address. According to `r1`'s routing table, it will send the broadcast to `r1-s2`, where it will be broadcasted to each of its node, which include host `c` and host `d`. These hosts do not forward it anywhere else because there are no other nodes.

**d. Is it seen on any interfaces of s1? Why or why not?**
It is not seen on the interface of `s1` because router `r1` has a routing table where the only match with `10.0.1.2` is the interface `r1-s2`.

**e. Was the ping successful?**
The ping reached its destination but received no response. 
![Alt text](exercise-6-ping.png)

## Question 7
Run the ip neigh command on `r1` to see the state of its ARP table: `ip neigh`


**What entries are in the table?**
![Alt text](exercise-7-neigh.png)
The connection is `STALE` because it timesout when a packet is sent to it. This is because there's no route from `c` to `r1`.

## Question 8
Follow the instructions from problem 5 to add the appropriate default route to host c, so it can send response messages to hosts outside its subnet. 

**Show the command you used.**
`sudo ip route add 0.0.0.0/0 via 10.0.1.1 dev c-s2`

## Question 9
Again run the following command on `a` to send a single packet from `a` to `c`: `ping -c 1 -W 1 10.0.1.2`

**Was it successful?**
![Alt text](exercise-9-ping.png)
Yes the ping was successful. Host `a` recieved a response from `c`. 

## Question 10

**What is the outcome of running the following on `a` and `c`, respectively?**
```
a$ ping -c 1 -W 1 10.0.3.2
c$ ping -c 1 -W 1 10.0.3.2
```


Neither of them work. It says that the `Destination Net Unreachable`. 
![Alt text](exercise-10-a-ping.png)
![Alt text](exercise-10-c-ping.png)

## Question 11

Take a look at the forwarding table entries for `r1` and `r2`. Note that they only have entries for the subnets for which they have interfaces. 

`r1` forwarding entries:
![Alt text](exercise-11-r1-entries.png)

`r2` forwarding entries:
![Alt text](exercise-11-r2-entries.png)

For `r1`, add entries for the specific subnets to which `r2` is directly connected, and vice-versa. You should use the ip route command that you used in question 5, but you will need to determine the appropriate IP prefixes, interface names, and next hop IP addresses, which will all be different for this one. Finally, add a forwarding entry for the default route to host e. This one will be more similar to what you did in question 5.

Taking a good look at the network diagram (i.e., net.png) will help you with this. Think carefully about what you are wanting to do in each case.

**a. Show the command you used to add the appropriate entry to r1.**
IP prefixes = `10.0.3.0/24`, interface names = `r1-r2`, and next hop IP addresses = `10.0.2.2` 

Command used: `sudo ip route add 10.0.3.0/24 via 10.0.2.2 dev r1-r2`


**b. Show the command you used to add the appropriate entries to r2.**
For subnet 1 (`s1`):
IP prefixes = `10.0.0.0/24`, interface names = `r2-r1`, and next hop IP addresses = `10.0.2.1` 
Command used: `sudo ip route add 10.0.0.0/24 via 10.0.2.1 dev r2-r1`

For subnet 2 (`s2`):
IP prefixes = `10.0.1.0/24`, interface names = `r2-r1`, and next hop IP addresses = `10.0.2.1` 

Command used: `sudo ip route add 10.0.1.0/24 via 10.0.2.1 dev r2-r1`


**c. Show the command you used to add the appropriate entry to e.**

IP prefixes = `default`, interface names = `e-s3`, and next hop IP addresses = `10.0.3.1` (router `r2`)
Command used: `sudo ip route add 0.0.0.0/0 via 10.0.3.1 dev e-s3`


## Question 12
**Now what is the outcome of running the following on a and c, respectively?**

```
a$ ping -c 1 -W 1 10.0.3.2
c$ ping -c 1 -W 1 10.0.3.2
```

Successful ping from `a` to `e`:
![Alt text](exercise-12-a-ping.png)


Successful ping from `c` to `e`:
![Alt text](exercise-12-c-ping.png)

We get the reponse, with rtt information. 

